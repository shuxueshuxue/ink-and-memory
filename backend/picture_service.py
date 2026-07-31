#!/usr/bin/env python3
# [Input] Database sessions, config (image API keys/models), requests library.
# [Output] Generated daily picture as base64 JPEG.
# [Pos] Shared picture generation service used by PolyCLI session_def and FastAPI route.
"""Shared daily picture generation logic."""

from datetime import datetime
from typing import Optional

import config
import database


def _today_in_tz(tz_name: str) -> str:
    from zoneinfo import ZoneInfo
    now = datetime.now(ZoneInfo(tz_name))
    return now.strftime("%Y-%m-%d")


def _generate_picture_for_date(
    user_id: int,
    target_date: Optional[str] = None,
    *,
    timezone: str = "Asia/Shanghai",
    notes_override: Optional[str] = None,
    skip_if_exists: bool = False,
    dry_run: bool = False,
):
    """
    Shared generator for daily pictures.

    - Extracts notes for the given date (or uses override).
    - Generates description + image.
    - Saves to DB unless dry_run=True.
    """
    target_date = target_date or _today_in_tz(timezone)
    target_date = target_date.strip()

    if skip_if_exists and not dry_run:
        existing = database.get_daily_pictures_range(user_id, target_date, target_date, limit=1)
        if existing:
            return {
                "skipped": True,
                "reason": "already exists",
                "date": target_date,
                "image_base64": existing[0]["base64"],
                "thumbnail_base64": existing[0]["base64"],
                "prompt": existing[0].get("prompt") or "",
            }

    notes = notes_override if notes_override is not None else database.extract_text_from_sessions_on_date(
        user_id, target_date, timezone
    )
    if not (notes or "").strip():
        return {
            "skipped": True,
            "reason": "no notes for date",
            "date": target_date,
            "image_base64": "",
            "thumbnail_base64": "",
            "prompt": "",
        }

    print(f"\n{'=' * 60}")
    print(f"🎨 generate_daily_picture() called")
    print(f"   Target date: {target_date}")
    print(f"{'=' * 60}\n")

    import requests

    # @@@ Fetch recent prompts to avoid duplication
    recent_prompts_text = ""
    try:
        db = database.get_db()
        recent_prompts = db.execute(
            "SELECT prompt FROM daily_pictures WHERE user_id = ? ORDER BY date DESC LIMIT 5",
            (user_id,),
        ).fetchall()
        db.close()

        if recent_prompts:
            recent_prompts_list = [p[0] for p in recent_prompts if p[0]]
            if recent_prompts_list:
                recent_prompts_text = "\n\nPREVIOUS IMAGE DESCRIPTIONS (do NOT repeat these themes/settings/objects):\n"
                for i, prompt in enumerate(recent_prompts_list, 1):
                    recent_prompts_text += f"{i}. {prompt}\n"
                recent_prompts_text += "\n⚠️ IMPORTANT: Create something COMPLETELY DIFFERENT from all previous descriptions above!\n"
                recent_prompts_text += "⚠️ Use different: setting, objects, style, mood, time of day, colors, composition.\n"
                recent_prompts_text += "⚠️ Be creative and avoid repetition!\n"
                print(f"📋 Found {len(recent_prompts_list)} recent prompts to avoid duplication")
    except Exception as e:
        print(f"⚠️ Could not fetch recent prompts: {e}")

    # Step 1: Convert notes to artistic image description using Claude Haiku
    description_prompt = f"""Read these personal notes and create a MINIMAL, SIMPLE image description.

Notes:
---
{notes}
---
{recent_prompts_text}
Create an EXTREMELY SIMPLE image description (1-2 sentences):
- ONE single object or element only (e.g., "a bird", "edge of a house", "a leaf")
- Clean white or simple solid color background
- Simple lines, minimal details
- Soft, gentle colors
- Style: simple line drawing, watercolor, or minimalist illustration

IMPORTANT RULES:
- Maximum 1-2 objects in the entire image
- No complex scenes, no multiple elements
- No detailed backgrounds
- Think: "one bird on white background" or "corner of a window, white space"
- Embrace empty space and simplicity

Examples of GOOD descriptions:
- "A single sparrow perched, simple brushstrokes, white background"
- "Corner of a window frame, soft blue, minimal details"
- "One maple leaf, watercolor, pale background"

Examples of BAD descriptions (TOO COMPLEX):
- "A desk with notebook, tea cup, lamp, and books" ❌
- "A room with furniture and decorations" ❌
- "Multiple objects or detailed scene" ❌

Return ONLY the minimal image description, no other text."""

    print("🧠 Creating image description from notes with Claude Haiku...")

    claude_response = requests.post(
        f"{config.IMAGE_API_ENDPOINT}/chat/completions",
        headers={
            "Authorization": f"Bearer {config.IMAGE_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": config.IMAGE_DESCRIPTION_MODEL,
            "messages": [{"role": "user", "content": description_prompt}],
            "max_tokens": config.IMAGE_DESCRIPTION_MAX_TOKENS,
        },
        timeout=config.IMAGE_DESCRIPTION_TIMEOUT,
    )

    if claude_response.status_code != 200:
        return {"image_base64": None, "error": "Failed to create image description", "date": target_date}

    claude_data = claude_response.json()
    image_description = (
        claude_data.get("choices", [{}])[0]
        .get("message", {})
        .get("content", "")
        .strip()
    )

    if not image_description:
        return {"image_base64": None, "error": "Failed to create image description", "date": target_date}

    print(f"📝 Image description: {image_description}")

    # Step 2: Generate image from description with retry logic
    url = f"{config.IMAGE_API_ENDPOINT}/chat/completions"
    headers = {
        "Authorization": f"Bearer {config.IMAGE_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": config.IMAGE_GENERATION_MODEL,
        "messages": [{"role": "user", "content": image_description}],
        "max_tokens": config.IMAGE_MAX_TOKENS,
    }

    # Retry logic with increasing timeouts
    for attempt in range(1, config.IMAGE_RETRY_MAX_ATTEMPTS + 1):
        try:
            timeout_seconds = (
                config.IMAGE_RETRY_BASE_TIMEOUT
                + (attempt - 1) * config.IMAGE_RETRY_TIMEOUT_INCREMENT
            )
            print(f"🎨 Generating image (attempt {attempt}/{config.IMAGE_RETRY_MAX_ATTEMPTS}, timeout={timeout_seconds}s)...")
            response = requests.post(
                url,
                headers=headers,
                json=payload,
                timeout=timeout_seconds,
            )

            if response.status_code != 200:
                print(f"❌ Error: {response.status_code}")
                if attempt < config.IMAGE_RETRY_MAX_ATTEMPTS:
                    print("⏳ Retrying in 2 seconds...")
                    import time

                    time.sleep(2)
                    continue
                return {"image_base64": None, "error": "Image generation failed", "date": target_date}

            data = response.json()

            # Extract image from response
            if "choices" in data and len(data["choices"]) > 0:
                message = data["choices"][0].get("message", {})
                images = message.get("images", [])

                if images:
                    image_data = images[0].get("image_url", {}).get("url", "")

                    if image_data.startswith("data:image/png;base64,"):
                        # Extract base64 data (without the data URI prefix)
                        base64_data = image_data.split(",", 1)[1]

                        # @@@ Convert to JPEG and create thumbnail
                        try:
                            import base64
                            from io import BytesIO
                            from PIL import Image

                            # Decode PNG
                            img_bytes = base64.b64decode(base64_data)
                            img = Image.open(BytesIO(img_bytes))

                            # Convert to RGB (JPEG doesn't support transparency)
                            if img.mode in ("RGBA", "LA", "P"):
                                rgb_img = Image.new("RGB", img.size, (255, 255, 255))
                                if img.mode == "RGBA":
                                    rgb_img.paste(img, mask=img.split()[-1])
                                else:
                                    rgb_img.paste(img)
                                img = rgb_img

                            # Full JPEG (quality 85)
                            full_output = BytesIO()
                            img.save(full_output, format="JPEG", quality=85, optimize=True)
                            full_jpeg = base64.b64encode(full_output.getvalue()).decode("utf-8")

                            # Thumbnail JPEG (400px width, quality 60)
                            thumb_width = 400
                            thumb_height = int(img.height * (thumb_width / img.width))
                            thumb_img = img.resize((thumb_width, thumb_height), Image.Resampling.LANCZOS)

                            thumb_output = BytesIO()
                            thumb_img.save(thumb_output, format="JPEG", quality=60, optimize=True)
                            thumb_jpeg = base64.b64encode(thumb_output.getvalue()).decode("utf-8")

                            print("✅ Image generated successfully")
                            print(f"   Original PNG: {len(base64_data)} chars")
                            print(f"   Full JPEG: {len(full_jpeg)} chars ({100 * len(full_jpeg) / len(base64_data):.1f}%)")
                            print(f"   Thumbnail: {len(thumb_jpeg)} chars ({100 * len(thumb_jpeg) / len(base64_data):.1f}%)")

                            result = {
                                "image_base64": full_jpeg,
                                "thumbnail_base64": thumb_jpeg,
                                "prompt": image_description,
                                "date": target_date,
                            }
                            if not dry_run:
                                database.save_daily_picture(
                                    user_id=user_id,
                                    date=target_date,
                                    image_base64=full_jpeg,
                                    prompt=image_description,
                                    thumbnail_base64=thumb_jpeg,
                                )
                            return result
                        except Exception as e:
                            print(f"⚠️ JPEG conversion failed: {e}, using original PNG")
                            result = {
                                "image_base64": base64_data,
                                "thumbnail_base64": base64_data,  # Fallback to full image
                                "prompt": image_description,
                                "date": target_date,
                            }
                            if not dry_run:
                                database.save_daily_picture(
                                    user_id=user_id,
                                    date=target_date,
                                    image_base64=base64_data,
                                    prompt=image_description,
                                    thumbnail_base64=base64_data,
                                )
                            return result

            if attempt < config.IMAGE_RETRY_MAX_ATTEMPTS:
                print("⚠️ No image in response, retrying...")
                import time

                time.sleep(2)
                continue
            return {"image_base64": None, "error": "No image in response", "date": target_date}

        except Exception as e:
            print(f"❌ Exception on attempt {attempt}: {e}")
            if attempt < config.IMAGE_RETRY_MAX_ATTEMPTS:
                print("⏳ Retrying in 2 seconds...")
                import time

                time.sleep(2)
                continue
            return {"image_base64": None, "error": str(e), "date": target_date}

    return {"image_base64": None, "error": "All retry attempts failed", "date": target_date}
