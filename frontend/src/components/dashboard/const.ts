export interface QuickActionCardItem {
  icon: 'envelope' | 'table' | 'calendar' | 'tasks' | 'calendarAlt' | 'database';
  title: string;
  description: string;
  prompt: string;
  color: 'success' | 'warning' | 'voice-blue' | 'voice-purple' | 'voice-pink' | 'voice-green';
}

export const QUICK_ACTION_CARDS: QuickActionCardItem[] = [
  {
    icon: 'envelope',
    title: '继续写作',
    description: '从当前段落继续扩展，保持原有语气与风格。',
    prompt: '请帮我继续写作，保持当前的写作风格和语气，自然衔接上下文。',
    color: 'success',
  },
  {
    icon: 'table',
    title: '总结笔记',
    description: '提炼核心观点，生成简洁的笔记摘要。',
    prompt: '请把当前笔记的核心内容总结成简洁的要点，突出最重要的想法。',
    color: 'warning',
  },
  {
    icon: 'calendar',
    title: '整理大纲',
    description: '将零散想法重组为清晰的结构化大纲。',
    prompt: '请帮我把这些想法整理成一个结构清晰的大纲，按逻辑分层排列。',
    color: 'voice-blue',
  },
  {
    icon: 'tasks',
    title: '发现关联',
    description: '找出笔记之间的联系与隐藏的共同主题。',
    prompt: '请分析这段内容，找出与其他可能相关的主题或概念之间的联系。',
    color: 'voice-purple',
  },
  {
    icon: 'calendarAlt',
    title: '写作灵感',
    description: '基于当前主题，提供创意角度与扩展方向。',
    prompt: '基于当前主题，给我几个有创意的写作角度或可以深入探索的方向。',
    color: 'voice-pink',
  },
  {
    icon: 'database',
    title: '回顾反思',
    description: '引导反思已有笔记，提出思考问题与行动建议。',
    prompt: '请帮我回顾这段笔记，提出几个值得深入思考的问题，并给出行动建议。',
    color: 'voice-green',
  },
];
