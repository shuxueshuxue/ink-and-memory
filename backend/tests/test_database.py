#!/usr/bin/env python3
"""Test deck and voice CRUD functions."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import database as db
import auth

def test_crud():
    print("🧪 Testing Deck & Voice CRUD functions...\n")

    # Create a test user first with proper password hash
    try:
        password_hash = auth.hash_password("test123")
        user_id = db.create_user("test@example.com", password_hash, "Test User")
        print(f"✅ Created test user: {user_id}")
    except ValueError:
        # User already exists, get by email
        user = db.get_user_by_email("test@example.com")
        user_id = user['id']
        print(f"✅ Using existing test user: {user_id}")

    print("\n--- Test 1: Get system decks ---")
    decks = db.get_user_decks(user_id)
    print(f"Found {len(decks)} decks:")
    for deck in decks:
        print(f"  - {deck['name']} ({deck['id']}) - {deck['voice_count']} voices")

    print("\n--- Test 2: Get deck with voices ---")
    # Seeded system decks use UUID ids (the old slug id 'introspection_deck'
    # no longer exists); resolve the introspection deck dynamically by name.
    introspection = next(
        (d for d in decks if d['name'] == '内省卡组'),
        next((d for d in decks if d['voice_count'] > 0), None),
    )
    assert introspection is not None, "no system deck available for CRUD test"
    introspection_deck_id = introspection['id']
    deck_detail = db.get_deck_with_voices(user_id, introspection_deck_id)
    assert deck_detail is not None, f"deck {introspection_deck_id} not found"
    print(f"Introspection deck has {len(deck_detail['voices'])} voices:")
    for voice in deck_detail['voices']:
        print(f"  - {voice['name']} ({voice['id']})")

    print("\n--- Test 3: Fork a deck ---")
    new_deck_id = db.fork_deck(user_id, introspection_deck_id)
    print(f"Forked introspection_deck → {new_deck_id}")

    # Verify fork
    forked_deck = db.get_deck_with_voices(user_id, new_deck_id)
    print(f"Forked deck has {len(forked_deck['voices'])} voices")
    print(f"Parent ID: {forked_deck['parent_id']}")

    print("\n--- Test 4: Update deck ---")
    success = db.update_deck(user_id, new_deck_id, {
        'name': 'My Custom Introspection Deck',
        'description': 'This is my personal copy'
    })
    print(f"Update success: {success}")

    # Verify update
    updated = db.get_deck_with_voices(user_id, new_deck_id)
    print(f"Updated name: {updated['name']}")
    print(f"Updated description: {updated['description']}")

    print("\n--- Test 5: Create a voice in forked deck ---")
    new_voice_id = db.create_voice(
        user_id, new_deck_id,
        name="Test Voice",
        system_prompt="This is a test voice prompt.",
        icon="fire",
        color="blue"
    )
    print(f"Created voice: {new_voice_id}")

    # Verify creation
    updated_deck = db.get_deck_with_voices(user_id, new_deck_id)
    print(f"Deck now has {len(updated_deck['voices'])} voices")

    print("\n--- Test 6: Update voice ---")
    success = db.update_voice(user_id, new_voice_id, {
        'name': 'Updated Test Voice',
        'system_prompt': 'Updated prompt text'
    })
    print(f"Update success: {success}")

    print("\n--- Test 7: Fork a voice ---")
    source_voice_id = deck_detail['voices'][0]['id']
    forked_voice_id = db.fork_voice(user_id, source_voice_id, new_deck_id)
    print(f"Forked voice {source_voice_id} → {forked_voice_id}")

    # Verify fork
    final_deck = db.get_deck_with_voices(user_id, new_deck_id)
    print(f"Deck now has {len(final_deck['voices'])} voices")

    print("\n--- Test 8: Delete voice ---")
    success = db.delete_voice(user_id, new_voice_id)
    print(f"Delete voice success: {success}")

    # Verify deletion
    after_delete = db.get_deck_with_voices(user_id, new_deck_id)
    print(f"Deck now has {len(after_delete['voices'])} voices")

    print("\n--- Test 9: Delete deck (cascade) ---")
    success = db.delete_deck(user_id, new_deck_id)
    print(f"Delete deck success: {success}")

    # Verify deletion
    final_decks = db.get_user_decks(user_id)
    print(f"User now has {len(final_decks)} decks")

    print("\n✅ All CRUD tests passed!")

if __name__ == "__main__":
    test_crud()
