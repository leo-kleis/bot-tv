/**
 * @typedef {Object} TwitchEmoteRef
 * @property {string} id
 * @property {string} text
 */

/**
 * @typedef {Object} ChatMessage
 * @property {string} [_uid]
 * @property {string} [id]
 * @property {string} [message_id]
 * @property {string} [user_id]
 * @property {string} [username]
 * @property {string} [display_name]
 * @property {string | null} [nickname]
 * @property {number[] | null} [color_rgb]
 * @property {string} [role]
 * @property {boolean} [is_bot]
 * @property {boolean} [is_moderator]
 * @property {boolean} [is_vip]
 * @property {boolean} [is_subscriber]
 * @property {string} [text]
 * @property {string} [message]
 * @property {string} timestamp
 * @property {TwitchEmoteRef[]} [emotes]
 * @property {false} [isSystem]
 */

/**
 * @typedef {Object} SystemEventPayload
 * @property {string} [timestamp]
 * @property {string} [user_id]
 * @property {string} [username]
 * @property {string} [display_name]
 * @property {string} [name]
 * @property {string | null} [nickname]
 * @property {string} [role]
 * @property {boolean} [is_bot]
 * @property {boolean} [is_moderator]
 * @property {boolean} [is_vip]
 * @property {boolean} [is_subscriber]
 * @property {string} [sub_tier]
 * @property {string} [url]
 * @property {string} [message]
 * @property {string} [from_display_name]
 * @property {number} [viewer_count]
 * @property {string} [tier]
 * @property {boolean} [is_gift]
 * @property {boolean} [is_anonymous]
 * @property {number} [total]
 * @property {number} [cumulative_total]
 * @property {number} [cumulative_months]
 * @property {number} [streak_months]
 * @property {number} [bits]
 * @property {string} [reward_title]
 * @property {number} [reward_cost]
 * @property {string} [user_input]
 * @property {string} [title]
 * @property {string[]} [outcomes]
 * @property {string} [winning_outcome_title]
 * @property {string} [status]
 * @property {boolean} [permanent]
 * @property {number} [duration_seconds]
 * @property {string} [reason]
 * @property {string} [moderator_name]
 */

/**
 * @typedef {Object} SystemChatMessage
 * @property {string} _uid
 * @property {true} isSystem
 * @property {string} type
 * @property {string} timestamp
 * @property {SystemEventPayload} data
 */

/**
 * @typedef {ChatMessage | SystemChatMessage} ChatEntry
 */

/**
 * @typedef {Object} IrcUser
 * @property {string} [user_id]
 * @property {string} [username]
 * @property {string} [display_name]
 * @property {string | null} [nickname]
 * @property {number[] | null} [color_rgb]
 * @property {string} [role]
 * @property {boolean} [is_bot]
 * @property {boolean} [is_moderator]
 * @property {boolean} [is_vip]
 * @property {boolean} [is_subscriber]
 * @property {string | null} [sub_tier]
 * @property {string} [timestamp]
 * @property {boolean} [present]
 * @property {string} [joinedAt]
 * @property {string | null} [partedAt]
 */

/**
 * @typedef {Map<string, IrcUser>} IrcUsersMap
 */

/**
 * @typedef {Object} StreamState
 * @property {boolean} online
 * @property {string} broadcasterName
 * @property {string} title
 * @property {string} category
 * @property {number | null} viewerCount
 * @property {number | null} viewerDiff
 * @property {string | null} startedAt
 */

/**
 * @typedef {Object} FollowerSyncData
 * @property {boolean} [is_first_sync]
 * @property {number} [total]
 * @property {number} [new_count]
 * @property {number} [lost_count]
 * @property {string[]} [new_labels]
 * @property {string[]} [lost_labels]
 * @property {string} [timestamp]
 */

/**
 * @typedef {Object} FollowerProgressData
 * @property {number} [fetched]
 * @property {number} [total]
 * @property {string} [message]
 */

/**
 * @typedef {Object} FollowersState
 * @property {FollowerSyncData | null} lastSync
 * @property {FollowerProgressData | null} progress
 * @property {number} [unreadCount]
 * @property {string[]} allNewLabels
 * @property {string[]} allLostLabels
 */

/**
 * @typedef {Object} ClipData
 * @property {string} url
 * @property {string} [timestamp]
 */

/**
 * @typedef {Object} AgentConversation
 * @property {string} timestamp
 * @property {string} question
 * @property {string | null} response
 * @property {string | null} model
 */

/**
 * @typedef {Object} ToastItem
 * @property {string} id
 * @property {string} type
 * @property {string} [title]
 * @property {boolean} [isError]
 * @property {boolean} [isWarning]
 * @property {SystemEventPayload} [data]
 */

/**
 * @typedef {Object} AppState
 * @property {boolean} connected
 * @property {boolean} historyLoaded
 * @property {boolean} initialLoad
 * @property {boolean} ircConnected
 * @property {StreamState} stream
 * @property {ChatEntry[]} chatMessages
 * @property {IrcUsersMap} ircUsers
 * @property {unknown[]} ircEvents
 * @property {FollowersState} followers
 * @property {ClipData[]} clips
 * @property {AgentConversation[]} agentConversations
 * @property {boolean} exited
 * @property {ToastItem[]} toasts
 */

/**
 * @typedef {Object} AppAction
 * @property {string} type
 * @property {AppAction[]} [events]
 * @property {Record<string, unknown>} [data]
 * @property {ToastItem} [toast]
 * @property {string} [id]
 */

/**
 * @typedef {(action: AppAction) => void} AppDispatch
 */

export {};
