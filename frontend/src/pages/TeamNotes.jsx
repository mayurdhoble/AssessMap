import { useState, useRef } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Send, MessageSquare } from 'lucide-react'
import api from '../api/client'

export default function TeamNotes() {
  const qc = useQueryClient()
  const [noteContent, setNoteContent] = useState('')
  const [noteQid, setNoteQid] = useState('')
  const [mentionAnchor, setMentionAnchor] = useState(null)
  const noteInputRef = useRef(null)
  const currentUser = localStorage.getItem('auth_user') || ''

  const { data: notesData, isLoading } = useQuery({
    queryKey: ['rq-notes'],
    queryFn: () => api.get('/v1/reported-questions/notes').then((r) => r.data),
    refetchInterval: 30000,
  })

  const { data: usersData } = useQuery({
    queryKey: ['rq-users'],
    queryFn: () => api.get('/auth/users').then((r) => r.data),
  })

  const postNote = useMutation({
    mutationFn: (body) => api.post('/v1/reported-questions/notes', body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['rq-notes'] })
      setNoteContent('')
      setNoteQid('')
      setMentionAnchor(null)
    },
  })

  const handleNoteInput = (e) => {
    const val = e.target.value
    setNoteContent(val)
    const cursorPos = e.target.selectionStart
    const before = val.slice(0, cursorPos)
    const match = before.match(/@([\w.@-]*)$/)
    setMentionAnchor(match ? { start: match.index, query: match[1] } : null)
  }

  const insertMention = (username) => {
    if (mentionAnchor === null) return
    const before = noteContent.slice(0, mentionAnchor.start)
    const after = noteContent.slice(mentionAnchor.start + 1 + mentionAnchor.query.length)
    setNoteContent(`${before}@${username} ${after}`)
    setMentionAnchor(null)
    noteInputRef.current?.focus()
  }

  const submitNote = () => {
    const content = noteContent.trim()
    if (!content) return
    const qid = noteQid ? parseInt(noteQid, 10) : null
    postNote.mutate({ content, question_issue_id: qid || null })
  }

  const filteredMentions = mentionAnchor !== null
    ? (usersData?.users || []).filter((u) =>
        u.toLowerCase().startsWith(mentionAnchor.query.toLowerCase()) && u !== currentUser
      )
    : []

  const notes = notesData?.items || []

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <h1 className="text-xl font-bold text-gray-800 flex items-center gap-2">
          <MessageSquare size={20} className="text-orange-500" />
          Team Notes
        </h1>
        {notesData?.total != null && (
          <span className="text-sm text-gray-400">{notesData.total} note{notesData.total !== 1 ? 's' : ''}</span>
        )}
      </div>

      {/* Composer */}
      <div className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-visible">
        {/* Top toolbar: Q# + user pills */}
        <div className="flex items-center gap-3 px-4 pt-4 pb-3 border-b border-gray-100 flex-wrap">
          <div className="flex items-center gap-2 shrink-0">
            <span className="text-xs font-medium text-gray-500">Link to Q#</span>
            <input
              type="number"
              value={noteQid}
              onChange={(e) => setNoteQid(e.target.value)}
              placeholder="optional issue ID"
              className="w-36 border border-gray-200 rounded-lg px-2.5 py-1.5 text-xs focus:outline-none focus:ring-1 focus:ring-orange-400"
            />
          </div>

          <div className="h-4 w-px bg-gray-200 shrink-0" />

          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-xs font-medium text-gray-500 shrink-0">Tag users:</span>
            {(usersData?.users || [])
              .filter((u) => u !== currentUser)
              .map((u) => (
                <button
                  key={u}
                  type="button"
                  onMouseDown={(e) => {
                    e.preventDefault()
                    const mention = `@${u} `
                    if (!noteContent.includes(mention)) {
                      setNoteContent((prev) => prev ? `${prev.trimEnd()} ${mention}` : mention)
                    }
                    noteInputRef.current?.focus()
                  }}
                  className="text-xs px-2.5 py-1 rounded-full border border-orange-200 bg-orange-50 text-orange-700 hover:bg-orange-100 transition-colors font-medium"
                >
                  @{u}
                </button>
              ))}
            {(usersData?.users || []).filter((u) => u !== currentUser).length === 0 && (
              <span className="text-xs text-gray-400 italic">No other users configured</span>
            )}
          </div>
        </div>

        {/* Message area */}
        <div className="relative p-4">
          <textarea
            ref={noteInputRef}
            value={noteContent}
            onChange={handleNoteInput}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); submitNote() }
              if (e.key === 'Escape') setMentionAnchor(null)
            }}
            placeholder="Write a message… type @username to tag someone. Enter to send, Shift+Enter for new line."
            rows={4}
            className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-1 focus:ring-orange-400 resize-none"
          />

          {/* @mention dropdown */}
          {filteredMentions.length > 0 && (
            <div className="absolute left-4 bottom-full mb-1 bg-white border border-gray-200 rounded-lg shadow-lg z-20 min-w-[180px]">
              {filteredMentions.map((u) => (
                <button
                  key={u}
                  className="block w-full text-left px-3 py-2 text-sm hover:bg-orange-50 hover:text-orange-700 first:rounded-t-lg last:rounded-b-lg transition-colors"
                  onMouseDown={(e) => { e.preventDefault(); insertMention(u) }}
                >
                  @{u}
                </button>
              ))}
            </div>
          )}

          <div className="flex items-center justify-between mt-2">
            <p className="text-xs text-gray-400">
              {noteQid ? <span className="text-orange-600 font-medium">Linked to Q#{noteQid}</span> : 'No question linked'}
            </p>
            <button
              onClick={submitNote}
              disabled={!noteContent.trim() || postNote.isPending}
              className="flex items-center gap-2 px-4 py-2 bg-orange-500 hover:bg-orange-600 text-white text-sm font-medium rounded-lg transition-colors disabled:opacity-40"
            >
              <Send size={14} />
              {postNote.isPending ? 'Sending…' : 'Send'}
            </button>
          </div>
        </div>
      </div>

      {/* Notes thread */}
      <div className="bg-white rounded-xl border border-gray-100 shadow-sm divide-y divide-gray-50">
        {isLoading && (
          <div className="py-10 text-center text-gray-400 text-sm">Loading notes…</div>
        )}
        {!isLoading && notes.length === 0 && (
          <div className="py-14 text-center">
            <MessageSquare size={32} className="text-gray-200 mx-auto mb-3" />
            <p className="text-gray-400 text-sm">No notes yet — be the first to write one!</p>
          </div>
        )}
        {notes.map((note) => (
          <div key={note.id} className="flex gap-4 px-5 py-4 hover:bg-gray-50/60 transition-colors">
            {/* Avatar */}
            <div className="w-9 h-9 rounded-full bg-orange-100 flex items-center justify-center text-orange-700 text-sm font-bold shrink-0">
              {(note.author[0] || '?').toUpperCase()}
            </div>

            {/* Body */}
            <div className="flex-1 min-w-0">
              <div className="flex items-baseline gap-2 flex-wrap mb-1">
                <span className="text-sm font-semibold text-gray-800">{note.author}</span>
                <span className="text-xs text-gray-400">
                  {new Date(note.created_at).toLocaleString('en-GB', {
                    day: '2-digit', month: 'short', year: 'numeric',
                    hour: '2-digit', minute: '2-digit',
                  })}
                </span>
                {note.question_issue_id && (
                  <span className="text-[11px] bg-orange-50 text-orange-600 px-2 py-0.5 rounded-full font-medium border border-orange-100">
                    Q#{note.question_issue_id}
                  </span>
                )}
              </div>
              <p className="text-sm text-gray-700 leading-relaxed break-words">
                {note.content.split(/(@\w+)/g).map((part, i) =>
                  part.startsWith('@')
                    ? <span key={i} className="text-orange-600 font-semibold">{part}</span>
                    : part
                )}
              </p>
              {note.tagged_users?.length > 0 && (
                <div className="flex flex-wrap gap-1 mt-1.5">
                  {note.tagged_users.map((u) => (
                    <span key={u} className="text-[11px] bg-orange-50 text-orange-600 px-1.5 py-0.5 rounded border border-orange-100">
                      @{u}
                    </span>
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
