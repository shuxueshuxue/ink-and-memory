import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';

const LANGUAGE_STORAGE_KEY = 'ink-language';

const resources = {
  en: {
    translation: {
      nav: {
        writing: 'Writing',
        timeline: 'Timeline',
        analysis: 'Reflections',
        decks: 'Decks',
        connector: 'Connector',
        chat: 'Chat',
        friends: 'Friends',
        settings: 'Settings'
      },
      settings: {
        heading: 'The Voice Council',
        subheading: 'Configure the inner voices that annotate everything you write.',
        tabs: {
          voices: '🎭 Voices',
          meta: '📜 Meta Prompt',
          states: '💭 User States'
        },
        language: {
          title: 'Interface Language',
          description: 'Choose which language the UI uses while your writing stays untouched.',
          placeholder: 'Select a language',
          preview: 'Changes apply immediately to menus, buttons, and helper copy.',
          options: {
            en: 'English',
            zh: '中文 (Chinese)'
          }
        }
      },
      analysis: {
        title: 'Reflections',
        subtitle: 'Patterns and insights woven through your words',
        backButton: 'Back',
        backTitle: 'Back to Dashboard',
        stats: {
          days: 'Days',
          entries: 'Entries',
          words: 'Words'
        },
        pastReflections: 'Past Reflections',
        report: {
          latest: 'Latest',
          patternCount: '{{count}} patterns'
        },
        actions: {
          generate: 'Generate New Analysis',
          generating: 'Reflecting...'
        },
        empty: {
          title: 'Your story awaits analysis',
          description: 'Begin the journey to discover the patterns, themes, and essence woven through your words'
        },
        papers: {
          echoes: { title: 'Recurring Themes', subtitle: 'Echoes' },
          traits: { title: 'Character Traits', subtitle: 'Personality' },
          patterns: { title: 'Behavioral Patterns', subtitle: 'Habits' }
        },
        statsLabels: {
          daysCount_one: '{{count}} day',
          daysCount_other: '{{count}} days',
          entriesCount_one: '{{count}} entry',
          entriesCount_other: '{{count}} entries',
          wordsCount: '{{value}} words'
        },
        reportCounts: {
          echoes_one: '{{count}} echo',
          echoes_other: '{{count}} echoes',
          traits_one: '{{count}} trait',
          traits_other: '{{count}} traits',
          patterns_one: '{{count}} pattern',
          patterns_other: '{{count}} patterns'
        }
      },
      deck: {
        heading: 'Voice Decks',
        subheading: 'Organize your inner voices into thematic collections',
        actions: {
          retry: 'Retry',
          create: '+ Create New Deck',
          creating: 'Creating...',
          addVoice: '+ Add Voice to this Deck',
          addingVoice: 'Adding...',
          install: 'Install',
          sync: 'Sync with Original',
          publish: 'Publish to Community',
          unpublish: 'Unpublish',
          delete: 'Delete Deck'
        },
        sections: {
          myDecks: 'My Decks',
          community: 'Community Decks ({{count}})'
        },
        labels: {
          system: 'System',
          noDescription: 'No description',
          voiceCount: '{{count}} voices',
          anonymous: 'Anonymous'
        },
        communityMeta: 'by {{author}} · {{voices}} voices · {{installs}} installs',
        communityEmpty: 'No published decks yet. Be the first to share!',
        confirm: {
          delete: 'Delete this deck and all its voices?',
          sync: 'Sync with original template? This will overwrite any changes you made to this deck.'
        },
        publishWarning: {
          heading: '⚠️ Publish Deck Warning',
          body: 'Publishing will <strong>break the parent link</strong>. This deck becomes a standalone deck in the community store.',
          note: 'This action cannot be undone. Even if you unpublish later, the parent link stays broken.',
          cancel: 'Cancel',
          confirm: 'Publish Anyway'
        },
        messages: {
          publishSuccess: '✅ Deck published to community!',
          unpublishSuccess: '✅ Deck unpublished',
          installSuccess: '✅ Deck installed to your collection!'
        }
      },
      timeline: {
        today: 'Today',
        generating: 'Generating...',
        entryCount_one: '{{count}} entry',
        entryCount_other: '{{count}} entries',
        friendSelector: {
          label: 'View Timeline',
          placeholder: 'Choose a friend',
          none: 'No friend selected',
          loading: 'Loading friends...',
          error: 'Could not load friends',
          button: 'Timeline settings',
          summarySolo: 'Personal timeline only',
          summaryWithFriend: 'Comparing with {{name}}',
          searchPlaceholder: 'Search friends',
          noFriends: 'You have no friends yet.',
          noMatches: 'No matches found',
          close: 'Close',
          personal: 'You',
          more: 'More',
          selfOnlyTitle: 'Just you today',
          selfOnlyHint: 'Pick a friend badge on the right to pull in their timeline beside yours.',
          friendEmptyTitle: 'No timeline yet',
          friendEmptyHint: 'This friend has not shared anything for these recent days.'
        },
        friendTimeline: {
          loading: 'Loading friend timeline...',
          empty: 'This friend has no entries yet.',
          error: 'Unable to load friend timeline.',
          readOnly: "Friend reflections open in read-only mode. You're just viewing their day.",
          readOnlyShort: 'Friend timeline preview'
        }
      },
      calendar: {
        title: 'Calendar',
        subtitle: 'Select a day to revisit your entries',
        empty: 'No entries yet. Start writing to fill this calendar.',
        deleteConfirm: 'Delete this entry?',
        entriesLabel_one: '{{count}} entry',
        entriesLabel_other: '{{count}} entries',
        currentEntryLabel: 'Current note',
        openButton: 'Open',
        deleteButton: 'Delete',
        close: 'Close',
        prev: '← Prev',
        next: 'Next →',
        noEntriesForDate: 'No entries for this date',
        todayLabel: 'Today',
        deleteError: 'Failed to delete entry'
      },
      friends: {
        myFriends: 'My Friends',
        requests: 'Requests',
        addFriend: 'Add Friend',
        noFriends: 'No friends yet. Use an invite code to add your first friend!',
        noRequests: 'No pending friend requests',
        loading: 'Loading...',
        viewTimeline: 'View Timeline',
        remove: 'Remove',
        accept: 'Accept',
        reject: 'Reject',
        generateInvite: 'Generate Invite Code',
        generateHint: 'Share this code with someone to let them send you a friend request. Code expires in 7 days.',
        generate: 'Generate Code',
        generating: 'Generating...',
        copy: 'Copy',
        codeCopied: 'Code copied to clipboard!',
        expiresAt: 'Expires',
        useInvite: 'Use Invite Code',
        useHint: 'Enter a friend\'s invite code to send them a friend request.',
        codePlaceholder: 'Enter 6-character code',
        send: 'Send Request',
        sending: 'Sending...',
        requestSent: 'Friend request sent!',
        confirmRemove: 'Remove this friend?',
        generateError: 'Failed to generate invite code',
        useCodeError: 'Invalid or expired code',
        acceptError: 'Failed to accept request',
        rejectError: 'Failed to reject request',
        removeError: 'Failed to remove friend'
      },
      chat: {
        quickActions: {
          generateImage: {
            label: 'Generate image',
            prompt: 'Generate an image with a consistent style based on the current content, suitable for inserting into the document.',
            description: 'Quickly generate an illustration for the current topic.'
          },
          writeEdit: {
            label: 'Write or edit',
            prompt: 'Help me write, rewrite, or polish the current content, keeping a natural tone consistent with the context.',
            description: 'Continue writing, rewriting, or polishing.'
          },
          findInfo: {
            label: 'Find information',
            prompt: 'Find relevant materials, references, and useful leads around the current topic.',
            description: 'Search for related materials and references.'
          }
        },
        dateGroup: {
          today: 'Today',
          yesterday: 'Yesterday',
          daysAgo_one: '{{count}} day ago',
          daysAgo_other: '{{count}} days ago',
          last7Days: 'Last 7 days',
          last30Days: 'Last 30 days',
          earlier: 'Earlier'
        },
        history: {
          newChat: 'New chat',
          newShort: 'New',
          creating: 'Creating',
          more: 'More',
          title: 'Chat history',
          subtitle: 'Pick a conversation to continue its context.',
          workspace: 'Workspace',
          share: 'Share',
          linkCopied: 'Link copied',
          createFailed: 'Failed to create the conversation. Please try again later.',
          fallbackTitle: 'New conversation',
          empty: 'No conversations yet',
          allShown: 'All conversations shown',
          deleteThread: 'Delete conversation',
          close: 'Close'
        },
        search: {
          button: 'Search',
          placeholder: 'Search chats...',
          searching: 'Searching...',
          noResults: 'No matching conversations',
          ariaLabel: 'Search chat history',
          closeAria: 'Close search'
        },
        tabs: {
          switcherAria: 'Chat workspace switcher',
          history: 'Chat history',
          connector: 'Resource connectors'
        },
        filters: {
          filterAll: 'Filter: All',
          sortRecent: 'Sort: Recent activity'
        },
        toolConfirmation: {
          userRejectedTool: 'User rejected the tool execution',
          userCancelledAnswer: 'User cancelled the question',
          askUserTitle: 'I&M needs your answer',
          confirmTitle: 'Allow I&M to call the {{tool}} tool',
          unknownTool: 'unknown',
          withSummary: ' — {{summary}}',
          pendingAnswer: 'Awaiting answer',
          pendingApproval: 'Awaiting approval',
          pendingConfirm: 'Pending',
          submit: 'Submit',
          cancel: 'Cancel',
          commandPrefix: 'Command: ',
          paramsPrefix: 'Parameters: ',
          reject: 'Reject',
          approve: 'Approve',
          submitting: 'Submitting…',
          processing: 'Processing…',
          answerSubmitted: 'Answer submitted',
          approved: 'Approved',
          cancelled: 'Cancelled',
          rejected: 'Rejected',
          networkConfirmTitle: 'Allow I&M to make a network request via {{tool}}',
          networkHostLabel: 'Host: ',
          networkHostUnknown: 'unknown (network shell command)',
          networkPolicyLabel: 'Network policy: ',
          networkPolicyAllowlist: 'Allowlist (domain not matched)',
          networkPolicyOpen: 'Open network (ask every time)'
        },
        askUser: {
          header: 'Your input is needed',
          selectOption: 'Select an option…',
          yes: 'Yes',
          fallbackQuestion: 'Please answer the question',
          questionNumber: 'Question {{number}}'
        },
        editorWrite: {
          userRejected: 'User rejected the editor write operation',
          loading: 'Loading…',
          processing: 'Processing…',
          accepted: 'Operation accepted',
          rejected: 'Operation rejected',
          reasonLabel: 'Reason',
          rejectReasonLabel: 'Rejection reason (optional)',
          rejectReasonPlaceholder: 'Explain why you are rejecting this to help the Agent adjust…',
          confirmReject: 'Confirm rejection',
          addRejectNote: 'Add a rejection note',
          rejectDirectly: 'Reject without a note',
          writeSegmentTitle: 'Agent suggests editing text content',
          targetSegmentId: 'Target segment ID',
          newContentPreview: 'New content preview',
          acceptChange: 'Accept change',
          reject: 'Reject',
          deleteSegmentTitle: 'Agent suggests deleting a segment (irreversible)',
          segmentToDeleteId: 'Segment ID to delete',
          irreversibleWarning: 'This action is irreversible. A deleted segment cannot be restored through tools.',
          confirmDelete: 'Confirm deletion',
          cancel: 'Cancel',
          insertWidgetTitle: 'Agent suggests inserting a widget',
          widgetType: 'Widget type',
          insertPosition: 'Insert position',
          afterSegment: 'After segment {{id}}',
          documentEnd: 'End of document',
          widgetData: 'Widget data',
          collapse: 'Collapse',
          expandFields: 'Expand ({{count}} fields)',
          acceptInsert: 'Accept insert',
          replyCommentTitle: 'Agent suggests replying to a voice comment',
          targetCommentId: 'Target comment ID',
          replyContent: 'Reply content',
          sendReply: 'Send reply',
          completed: {
            writeSegment: 'Content written',
            deleteSegment: 'Segment deleted',
            insertWidget: 'Widget inserted',
            replyComment: 'Comment replied'
          },
          success: 'Success',
          failure: 'Failed',
          segmentIdPrefix: 'Segment ID: ',
          jumpToNote: 'Jump to note',
          fallbackTitle: 'Agent requests an editor operation: ',
          accept: 'Accept'
        },
        inputDock: {
          toolChoiceAuto: 'Auto',
          toolChoiceAutoTitle: 'Claude decides when to call tools',
          toolChoiceManual: 'Confirm each step',
          toolChoiceManualTitle: 'Every tool call requires manual confirmation',
          workspaceSyncFailed: 'Failed to sync the file to the workspace',
          uploadFailed: 'Upload failed',
          fileTooLarge: '{{name}}: file too large (max {{max}})',
          waitForUpload: 'Please wait for file uploads to finish',
          deleteFileAria: 'Delete file {{name}}',
          uploadHint: 'Upload: paste · drag & drop · click to browse',
          sendShortcut: '⌘ / Ctrl + Enter to send',
          inputAria: 'Chat input',
          addAttachmentAria: 'Add attachment',
          addAttachment: '+ Attachment',
          toolAccessAria: 'Tool call permission',
          toolModeAria: 'Tool call mode',
          fullAccess: 'Full access',
          stopping: 'Stopping',
          stopGenerating: 'Stop generating',
          generating: 'Generating',
          waitingUpload: 'Waiting for uploads…',
          send: 'Send',
          sendAria: 'Send message'
        },
        panel: {
          scrollToBottom: 'Scroll to bottom'
        },
        planPanel: {
          planning: 'Planning',
          exited: 'Exited planning',
          justNow: 'Just now',
          minutesAgo_one: '{{count}} minute ago',
          minutesAgo_other: '{{count}} minutes ago',
          hoursAgo_one: '{{count}} hour ago',
          hoursAgo_other: '{{count}} hours ago',
          daysAgo_one: '{{count}} day ago',
          daysAgo_other: '{{count}} days ago',
          waitingContent: 'Planning triggered, waiting for plan content…',
          noContent: 'No plan content found.',
          loading: 'Loading…',
          loadFull: 'Content truncated — click to load the full plan',
          noTodos: 'No to-dos yet',
          collapse: 'Collapse',
          expandMore: 'Show {{count}} more',
          buttonAria: 'Plan & to-dos',
          tooltip: 'Plan & to-dos',
          planTitle: 'Plan',
          todosTitle: 'To-dos'
        },
        mermaid: {
          renderFailed: 'Mermaid · render failed',
          rendering: 'Mermaid · rendering…',
          preview: 'Preview',
          source: 'Source',
          copySource: 'Copy Markdown source',
          exportPng: 'Export PNG'
        },
        connector: {
          noInteraction: 'No interactions yet',
          status: {
            notConnected: 'Not connected',
            healthy: 'Healthy',
            authenticating: 'Authenticating',
            expired: 'Expired',
            error: 'Error'
          },
          auth: {
            authenticated: 'Authorized',
            authenticating: 'Authorizing',
            expired: 'Authorization expired',
            error: 'Authorization error',
            unauthorized: 'Not authorized'
          },
          sync: {
            syncing: 'Syncing',
            synced: 'Synced',
            waitingAuth: 'Awaiting authorization',
            reauthNeeded: 'Re-authorization needed',
            error: 'Sync error',
            mounted: 'Mounted',
            notSynced: 'Not synced',
            pendingSync: 'Pending sync'
          },
          statAuth: 'Auth',
          statSync: 'Sync',
          statResources: 'Resources',
          resourceCount: '{{count}}',
          lastInteraction: 'Last activity {{time}}',
          manage: 'Manage',
          linkedResources: 'Linked resources',
          noLinkedResources: 'No linked resources yet',
          showingProgress: 'Showing {{shown}} of {{total}} — scroll down to load more',
          showingAll: 'Showing all {{count}} resources',
          emptyTitle: 'No resource connectors yet',
          emptyDescription: 'Connect Notion / Feishu / CLI to use resources in conversations',
          selectConnector: 'Choose a connector',
          loadFailed: 'Failed to load connector status'
        },
        shellError: {
          history: 'Chat history',
          connector: 'Connectors'
        },
        skeleton: {
          loading: 'Loading'
        },
        upload: {
          serverFailed: 'Server upload failed',
          noFileKey: 'Server did not return a file key',
          parseFailed: 'Failed to parse the upload result',
          failed: 'Upload failed',
          fileRequired: 'A file is required for upload',
          storageLoading: 'Storage service is still loading, please try again later',
          storageNotConfigured: 'Storage service is not configured'
        }
      }
    }
  },
  zh: {
    translation: {
      nav: {
        writing: '写作',
        timeline: '时间线',
        analysis: '回顾',
        decks: '卡组',
        connector: '连接器',
        chat: '对话',
        friends: '好友',
        settings: '设置'
      },
      settings: {
        heading: '心灵议会',
        subheading: '在这里整理那些会对你文字发表评论的声音。',
        tabs: {
          voices: '🎭 声线',
          meta: '📜 元提示',
          states: '💭 心情状态'
        },
        language: {
          title: '界面语言',
          description: '切换界面上的文字语言，日记内容保持原样。',
          placeholder: '选择语言',
          preview: '切换后菜单、按钮与说明会立即更新。',
          options: {
            en: 'English (英语)',
            zh: '中文'
          }
        }
      },
      analysis: {
        title: '回顾',
        subtitle: '读出文字里编织的脉络与启示',
        backButton: '返回',
        backTitle: '回到总览',
        stats: {
          days: '天数',
          entries: '篇章',
          words: '字数'
        },
        pastReflections: '历史回顾',
        report: {
          latest: '最新',
          patternCount: '{{count}} 个模式'
        },
        actions: {
          generate: '生成全新分析',
          generating: '解析中...'
        },
        empty: {
          title: '等待解析的故事',
          description: '开始探索文字里反复出现的主题、情绪与线索'
        },
        papers: {
          echoes: { title: '重复回响', subtitle: '主题回声' },
          traits: { title: '性格折射', subtitle: '个性印象' },
          patterns: { title: '行为轨迹', subtitle: '惯性与习惯' }
        },
        statsLabels: {
          daysCount_one: '{{count}} 天',
          daysCount_other: '{{count}} 天',
          entriesCount_one: '{{count}} 篇章',
          entriesCount_other: '{{count}} 篇章',
          wordsCount: '{{value}} 字'
        },
        reportCounts: {
          echoes_one: '{{count}} 个回声',
          echoes_other: '{{count}} 个回声',
          traits_one: '{{count}} 个性格',
          traits_other: '{{count}} 个性格',
          patterns_one: '{{count}} 个模式',
          patterns_other: '{{count}} 个模式'
        }
      },
      deck: {
          heading: '声线卡组',
          subheading: '以主题整理你的心灵声线',
          actions: {
            retry: '重试',
            create: '+ 新建卡组',
            creating: '建立中...',
            addVoice: '+ 向卡组添加声线',
            addingVoice: '添加中...',
            install: '安装',
            sync: '与原版同步',
            publish: '发布到社区',
            unpublish: '取消发布',
            delete: '删除卡组'
          },
        sections: {
          myDecks: '我的卡组',
          community: '社区卡组（{{count}}）'
        },
        labels: {
          system: '系统',
          noDescription: '暂无简介',
          voiceCount: '{{count}} 条声线',
          anonymous: '匿名'
        },
        communityMeta: '由 {{author}} 创作 · {{voices}} 条声线 · {{installs}} 次安装',
        communityEmpty: '尚无公开卡组，来做第一位分享的人吧！',
        confirm: {
          delete: '确定删除这个卡组以及所有声线？',
          sync: '与原模板同步？这会覆盖你在卡组里的修改。'
        },
        publishWarning: {
          heading: '⚠️ 发布提醒',
          body: '发布后会<strong>断开与父卡组的链接</strong>，并在社区中以独立卡组存在。',
          note: '此操作不可逆，就算之后取消发布，父子链接也无法恢复。',
          cancel: '取消',
          confirm: '仍要发布'
        },
        messages: {
          publishSuccess: '✅ 已发布到社区！',
          unpublishSuccess: '✅ 已取消发布',
          installSuccess: '✅ 已安装到你的卡组'
        }
      },
      timeline: {
        today: '今天',
        generating: '生成中...',
        entryCount_one: '{{count}} 条记录',
        entryCount_other: '{{count}} 条记录',
        friendSelector: {
          label: '查看时间线',
          placeholder: '选择好友',
          none: '不查看好友',
          loading: '正在加载好友...',
          error: '无法加载好友列表',
          button: '时间线设置',
          summarySolo: '当前仅显示个人时间线',
          summaryWithFriend: '正在与 {{name}} 的时间线对照',
          searchPlaceholder: '搜索好友',
          noFriends: '你还没有好友。',
          noMatches: '没有符合条件的好友',
          close: '关闭',
          personal: '仅自己',
          more: '更多',
          selfOnlyTitle: '只有你在这里',
          selfOnlyHint: '点右侧的好友圆标，就能把 TA 的时间线拉来并排浏览。',
          friendEmptyTitle: '最近没有内容',
          friendEmptyHint: '这位好友在最近几天都没有留下时间线。'
        },
        friendTimeline: {
          loading: '正在加载好友时间线...',
          empty: '这位好友最近没有记录。',
          error: '无法加载好友的时间线。',
          readOnly: '好友的总结仅供查看，无法互动。',
          readOnlyShort: '好友时间线预览'
        }
      },
      calendar: {
        title: '日历',
        subtitle: '选择任意一天重新回到当时的文字',
        empty: '这里还没有记录，动笔就会留下足迹。',
        deleteConfirm: '确定删除这篇记录？',
        entriesLabel_one: '{{count}} 篇',
        entriesLabel_other: '{{count}} 篇',
        currentEntryLabel: '当前笔记',
        openButton: '打开',
        deleteButton: '删除',
        close: '关闭',
        prev: '← 上个月',
        next: '下个月 →',
        noEntriesForDate: '这一天暂无记录',
        todayLabel: '今天',
        deleteError: '删除失败'
      },
      friends: {
        myFriends: '我的好友',
        requests: '好友申请',
        addFriend: '添加好友',
        noFriends: '还没有好友。使用邀请码添加你的第一个好友吧！',
        noRequests: '暂无待处理的好友申请',
        loading: '加载中...',
        viewTimeline: '查看时间线',
        remove: '移除',
        accept: '接受',
        reject: '拒绝',
        generateInvite: '生成邀请码',
        generateHint: '将此邀请码分享给朋友，让对方向你发送好友申请。邀请码 7 天后过期。',
        generate: '生成邀请码',
        generating: '生成中...',
        copy: '复制',
        codeCopied: '邀请码已复制到剪贴板！',
        expiresAt: '过期时间',
        useInvite: '使用邀请码',
        useHint: '输入朋友的邀请码，向对方发送好友申请。',
        codePlaceholder: '输入 6 位邀请码',
        send: '发送申请',
        sending: '发送中...',
        requestSent: '好友申请已发送！',
        confirmRemove: '确定要移除这位好友吗？',
        generateError: '生成邀请码失败',
        useCodeError: '邀请码无效或已过期',
        acceptError: '接受申请失败',
        rejectError: '拒绝申请失败',
        removeError: '移除好友失败'
      },
      chat: {
        quickActions: {
          generateImage: {
            label: '生成图片',
            prompt: '请根据当前内容生成一张风格统一、适合插入文档的图片。',
            description: '根据当前主题快速生成配图。'
          },
          writeEdit: {
            label: '撰写或编辑',
            prompt: '请帮我撰写、改写或润色当前内容，保持自然语气和上下文一致。',
            description: '继续写作、改写或润色。'
          },
          findInfo: {
            label: '查找资料',
            prompt: '请围绕当前主题查找相关资料、参考信息和可用线索。',
            description: '检索相关资料和参考。'
          }
        },
        dateGroup: {
          today: '今天',
          yesterday: '昨天',
          daysAgo_one: '{{count}} 天前',
          daysAgo_other: '{{count}} 天前',
          last7Days: '前 7 天',
          last30Days: '前 30 天',
          earlier: '更早'
        },
        history: {
          newChat: '新建对话',
          newShort: '新建',
          creating: '创建中',
          more: '更多',
          title: '历史对话',
          subtitle: '选择一条对话继续上下文。',
          workspace: '工作空间',
          share: '分享',
          linkCopied: '已复制链接',
          createFailed: '创建对话失败，请稍后再试。',
          fallbackTitle: '新对话',
          empty: '暂无会话',
          allShown: '已显示全部会话',
          deleteThread: '删除对话',
          close: '关闭'
        },
        search: {
          button: '搜索',
          placeholder: '搜索聊天...',
          searching: '搜索中...',
          noResults: '未找到匹配会话',
          ariaLabel: '搜索历史对话',
          closeAria: '关闭搜索'
        },
        tabs: {
          switcherAria: 'Chat 工作区切换',
          history: '聊天历史',
          connector: '资源连接器'
        },
        filters: {
          filterAll: '筛选：全部',
          sortRecent: '排序：最近交互'
        },
        toolConfirmation: {
          userRejectedTool: '用户拒绝执行工具',
          userCancelledAnswer: '用户取消了问题回答',
          askUserTitle: 'I&M 需要你的回答',
          confirmTitle: '是否允许 I&M 调用 {{tool}} 工具',
          unknownTool: '未知',
          withSummary: '，{{summary}}',
          pendingAnswer: '待回答',
          pendingApproval: '待授权',
          pendingConfirm: '待确认',
          submit: '提交',
          cancel: '取消',
          commandPrefix: '命令：',
          paramsPrefix: '参数：',
          reject: '拒绝',
          approve: '同意',
          submitting: '提交中…',
          processing: '处理中…',
          answerSubmitted: '答案已提交',
          approved: '已同意',
          cancelled: '已取消',
          rejected: '已拒绝',
          networkConfirmTitle: '是否允许 I&M 通过 {{tool}} 发起网络请求',
          networkHostLabel: '目标主机：',
          networkHostUnknown: '未知（网络类命令）',
          networkPolicyLabel: '网络策略：',
          networkPolicyAllowlist: '白名单（域名未命中）',
          networkPolicyOpen: '开放网络（每次询问）'
        },
        askUser: {
          header: '需要你的输入',
          selectOption: '请选择…',
          yes: '是',
          fallbackQuestion: '请回答问题',
          questionNumber: '问题 {{number}}'
        },
        editorWrite: {
          userRejected: '用户拒绝了编辑器写操作',
          loading: '加载中…',
          processing: '处理中…',
          accepted: '操作已接受',
          rejected: '操作已拒绝',
          reasonLabel: '操作理由',
          rejectReasonLabel: '拒绝理由（可选）',
          rejectReasonPlaceholder: '说明拒绝原因，帮助 Agent 调整方案…',
          confirmReject: '确认拒绝',
          addRejectNote: '添加拒绝说明',
          rejectDirectly: '不添加说明，直接拒绝',
          writeSegmentTitle: 'Agent 建议修改文字内容',
          targetSegmentId: '目标片段 ID',
          newContentPreview: '新内容预览',
          acceptChange: '接受修改',
          reject: '拒绝',
          deleteSegmentTitle: 'Agent 建议删除片段（不可逆操作）',
          segmentToDeleteId: '将删除片段 ID',
          irreversibleWarning: '此操作不可逆，片段删除后无法通过工具恢复。',
          confirmDelete: '确认删除',
          cancel: '取消',
          insertWidgetTitle: 'Agent 建议插入组件',
          widgetType: '组件类型',
          insertPosition: '插入位置',
          afterSegment: '片段 {{id}} 之后',
          documentEnd: '文档末尾',
          widgetData: '组件数据',
          collapse: '收起',
          expandFields: '展开（{{count}} 个字段）',
          acceptInsert: '接受插入',
          replyCommentTitle: 'Agent 建议回复语音评论',
          targetCommentId: '目标评论 ID',
          replyContent: '回复内容',
          sendReply: '发送回复',
          completed: {
            writeSegment: '已写入内容',
            deleteSegment: '已删除片段',
            insertWidget: '已插入组件',
            replyComment: '已回复评论'
          },
          success: '成功',
          failure: '失败',
          segmentIdPrefix: '片段 ID：',
          jumpToNote: '跳转到笔记',
          fallbackTitle: 'Agent 请求执行编辑器操作：',
          accept: '接受'
        },
        inputDock: {
          toolChoiceAuto: '自动',
          toolChoiceAutoTitle: 'Claude 自主决定是否调用工具',
          toolChoiceManual: '逐步确认',
          toolChoiceManualTitle: '每次工具调用都需要手动确认',
          workspaceSyncFailed: '工作空间文件同步失败',
          uploadFailed: '上传失败',
          fileTooLarge: '{{name}}: 文件过大 (最大 {{max}})',
          waitForUpload: '请等待文件上传完成',
          deleteFileAria: '删除文件 {{name}}',
          uploadHint: '上传方式：粘贴 · 拖拽 · 点击选择',
          sendShortcut: '⌘ / Ctrl + Enter 发送',
          inputAria: '聊天输入',
          addAttachmentAria: '添加附件',
          addAttachment: '+ 附件',
          toolAccessAria: '工具调用权限',
          toolModeAria: '工具调用模式',
          fullAccess: '完全访问',
          stopping: '正在停止',
          stopGenerating: '停止生成',
          generating: '生成中',
          waitingUpload: '等待上传完成…',
          send: '发送',
          sendAria: '发送消息'
        },
        panel: {
          scrollToBottom: '滚动到底部'
        },
        planPanel: {
          planning: '规划中',
          exited: '已退出规划',
          justNow: '刚刚',
          minutesAgo_one: '{{count}} 分钟前',
          minutesAgo_other: '{{count}} 分钟前',
          hoursAgo_one: '{{count}} 小时前',
          hoursAgo_other: '{{count}} 小时前',
          daysAgo_one: '{{count}} 天前',
          daysAgo_other: '{{count}} 天前',
          waitingContent: '规划已触发，等待计划内容…',
          noContent: '未找到计划内容。',
          loading: '加载中…',
          loadFull: '内容已截断，点击加载完整',
          noTodos: '暂无待办',
          collapse: '收起',
          expandMore: '展开 {{count}} 个',
          buttonAria: '计划与待办',
          tooltip: '计划与待办',
          planTitle: '计划',
          todosTitle: '待办'
        },
        mermaid: {
          renderFailed: 'Mermaid · 渲染失败',
          rendering: 'Mermaid · 渲染中…',
          preview: '预览',
          source: '源码',
          copySource: '复制 Markdown 源码',
          exportPng: '导出 PNG'
        },
        connector: {
          noInteraction: '暂无交互',
          status: {
            notConnected: '未连接',
            healthy: '健康',
            authenticating: '认证中',
            expired: '已过期',
            error: '异常'
          },
          auth: {
            authenticated: '已授权',
            authenticating: '授权中',
            expired: '授权过期',
            error: '授权异常',
            unauthorized: '未授权'
          },
          sync: {
            syncing: '同步中',
            synced: '已同步',
            waitingAuth: '等待授权',
            reauthNeeded: '待重新授权',
            error: '同步异常',
            mounted: '已挂载',
            notSynced: '未同步',
            pendingSync: '待同步'
          },
          statAuth: '授权',
          statSync: '同步',
          statResources: '资源',
          resourceCount: '{{count}} 个',
          lastInteraction: '最近交互 {{time}}',
          manage: '管理',
          linkedResources: '已链接资源',
          noLinkedResources: '暂无已链接资源',
          showingProgress: '已显示 {{shown}} / {{total}}，继续向下滚动加载更多',
          showingAll: '已显示全部 {{count}} 个资源',
          emptyTitle: '暂无资源连接器',
          emptyDescription: '连接 Notion / 飞书 / CLI 后可在对话中使用资源',
          selectConnector: '选择连接器',
          loadFailed: '连接器状态读取失败'
        },
        shellError: {
          history: '历史对话',
          connector: '连接器'
        },
        skeleton: {
          loading: '加载中'
        },
        upload: {
          serverFailed: '服务器上传失败',
          noFileKey: '服务器未返回文件 key',
          parseFailed: '解析上传结果失败',
          failed: '上传失败',
          fileRequired: '上传需要一个文件',
          storageLoading: '存储服务正在加载，请稍后再试',
          storageNotConfigured: '存储服务未配置'
        }
      }
    }
  }
};

const fallback = 'en';

function getInitialLanguage(): string {
  if (typeof window === 'undefined') {
    return fallback;
  }
  return localStorage.getItem(LANGUAGE_STORAGE_KEY) || fallback;
}

i18n
  .use(initReactI18next)
  .init({
    resources,
    lng: getInitialLanguage(),
    fallbackLng: fallback,
    interpolation: {
      escapeValue: false
    }
  });

if (typeof window !== 'undefined') {
  i18n.on('languageChanged', (lng) => {
    try {
      localStorage.setItem(LANGUAGE_STORAGE_KEY, lng);
    } catch (error) {
      console.warn('Failed to persist language preference:', error);
    }
  });
}

export { LANGUAGE_STORAGE_KEY };
export function getDateLocale(language?: string | null): string {
  if (!language) return 'en-US';
  return language.startsWith('zh') ? 'zh-CN' : 'en-US';
}

export default i18n;
