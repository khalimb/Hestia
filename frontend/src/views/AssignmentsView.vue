<script setup>
import { ref, onMounted } from 'vue'
import { format, parseISO } from 'date-fns'
import { useAgentStore } from '../stores/agents'

// Modelled on Hierophant's project Assignments section: start a doc, paste the
// copied prompt into an agent, give the brief, and the agent saves the
// deliverable back here via MCP (or the fallback PATCH). Refresh to see it.
const agents = useAgentStore()

const newTitle = ref('')
const starting = ref(false)
const notice = ref('')
const noticeError = ref(false)
let noticeTimer = null

const promptPreview = ref('')     // shown when the clipboard is unavailable
const showPromptPreview = ref(false)

const modalShow = ref(false)
const modalTitle = ref('')
const modalSummary = ref('')
const modalContent = ref('')

onMounted(() => {
  refresh()
})

async function refresh() {
  try {
    await agents.fetchAssignments()
  } catch {
    flash('Failed to load assignments.', true)
  }
}

function flash(message, isError = false) {
  notice.value = message
  noticeError.value = isError
  clearTimeout(noticeTimer)
  noticeTimer = setTimeout(() => { notice.value = '' }, isError ? 8000 : 5000)
}

async function copyAndNotify(prompt, message) {
  try {
    await navigator.clipboard.writeText(prompt)
    showPromptPreview.value = false
    flash(message)
  } catch {
    // Clipboard blocked (e.g. non-secure context) — show the prompt for manual copy.
    promptPreview.value = prompt
    showPromptPreview.value = true
    flash("Couldn't reach the clipboard — copy the prompt from the box below.", true)
  }
}

async function startAssignment() {
  starting.value = true
  try {
    const data = await agents.createAssignment(newTitle.value.trim())
    newTitle.value = ''
    await copyAndNotify(
      data.rendered_prompt,
      'Assignment prompt copied — paste it into your agent and give the brief. Click Refresh once it saves.',
    )
  } catch (e) {
    flash('Failed to start assignment: ' + (e.response?.data?.detail || e.message), true)
  } finally {
    starting.value = false
  }
}

async function openAssignment(a) {
  if (a.status === 'POPUL' || a.has_content) {
    try {
      const data = await agents.fetchAssignment(a.id)
      modalTitle.value = data.title || 'Untitled assignment'
      modalSummary.value = data.summary || ''
      modalContent.value = data.content || ''
      modalShow.value = true
    } catch {
      flash('Failed to load the deliverable.', true)
    }
  } else {
    await resumeAssignment(a)
  }
}

async function resumeAssignment(a) {
  try {
    const prompt = await agents.fetchAssignmentPrompt(a.id)
    await copyAndNotify(prompt, 'Prompt copied again — paste it into your agent to resume.')
  } catch {
    flash('Failed to build the prompt.', true)
  }
}

async function removeAssignment(a) {
  if (!confirm(`Delete assignment "${a.title || 'Untitled'}"? This cannot be undone.`)) return
  try {
    await agents.deleteAssignment(a.id)
  } catch {
    flash('Failed to delete assignment.', true)
  }
}

function statusLabel(status) {
  return status === 'POPUL' ? 'Saved' : 'Awaiting deliverable'
}

function statusClass(status) {
  return status === 'POPUL' ? 'badge badge-paid' : 'badge badge-pending'
}

function formatDate(iso) {
  return iso ? format(parseISO(iso), 'dd MMM yyyy HH:mm') : ''
}
</script>

<template>
  <div>
    <div class="page-header">
      <div>
        <h1>Assignments</h1>
        <p class="text-sm text-muted">Deliverables produced by an agent connected to Hestia: bill reviews, budget drafts, reconciliations, bulk edits.</p>
      </div>
      <button class="btn btn-outline" :disabled="agents.loading" @click="refresh">
        {{ agents.loading ? 'Refreshing...' : 'Refresh' }}
      </button>
    </div>

    <div v-if="notice" :class="['alert', noticeError ? 'alert-danger' : 'alert-success']">{{ notice }}</div>

    <!-- New assignment -->
    <div class="card mb-4">
      <div class="card-body">
        <div class="flex gap-2 items-center" style="flex-wrap:wrap">
          <input
            v-model="newTitle"
            type="text"
            class="form-input"
            style="flex:1; min-width:240px"
            placeholder="Assignment topic (optional), e.g. October bill review"
            @keyup.enter="startAssignment"
          />
          <button class="btn btn-primary" :disabled="starting" @click="startAssignment">
            {{ starting ? 'Starting...' : '+ New assignment' }}
          </button>
        </div>
        <p class="text-xs text-muted mt-1">
          Creates a deliverable doc and copies a ready-to-paste prompt to your clipboard. Paste it into Claude
          (with the Hestia MCP connector from Settings), give the brief, and the agent saves the deliverable back
          here — then click Refresh. The prompt template is editable in Settings.
        </p>
        <div v-if="showPromptPreview" style="margin-top:0.75rem">
          <textarea
            :value="promptPreview"
            readonly
            class="form-input"
            rows="10"
            style="font-family:'SF Mono',Monaco,monospace; font-size:0.8125rem"
            @focus="$event.target.select()"
          ></textarea>
        </div>
      </div>
    </div>

    <!-- List -->
    <div v-if="!agents.assignments.length && !agents.loading" class="empty-state">
      <h3>No assignments yet</h3>
      <p>Start one above to get a prompt for your agent.</p>
    </div>

    <div v-else class="card">
      <div class="card-body" style="padding:0">
        <table>
          <thead>
            <tr>
              <th>Status</th>
              <th>Assignment</th>
              <th>Started</th>
              <th>By</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="a in agents.assignments" :key="a.id">
              <td><span :class="statusClass(a.status)">{{ statusLabel(a.status) }}</span></td>
              <td>
                <a href="#" @click.prevent="openAssignment(a)" style="color:var(--color-primary); font-weight:500; text-decoration:none">
                  {{ a.title || 'Untitled assignment' }}
                </a>
                <p v-if="a.summary" class="text-xs text-muted" style="margin-top:0.125rem">{{ a.summary }}</p>
                <p v-if="a.populated_at" class="text-xs text-muted">saved {{ formatDate(a.populated_at) }}</p>
              </td>
              <td class="text-sm text-muted">{{ formatDate(a.started_at) }}</td>
              <td class="text-sm">{{ a.created_by_name }}</td>
              <td class="text-right" style="white-space:nowrap">
                <button class="btn btn-sm btn-outline" @click="resumeAssignment(a)">Copy prompt</button>
                <button class="btn btn-sm btn-outline" style="margin-left:0.25rem; color:var(--color-danger)" @click="removeAssignment(a)">Delete</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Deliverable modal -->
    <div v-if="modalShow" class="modal-overlay" @click.self="modalShow = false">
      <div class="modal" style="max-width:860px; width:95%">
        <div class="modal-header">
          <div>
            <h3>{{ modalTitle }}</h3>
            <p v-if="modalSummary" class="text-xs text-muted">{{ modalSummary }}</p>
          </div>
          <button @click="modalShow = false" class="btn btn-sm btn-outline">&times;</button>
        </div>
        <div class="modal-body" style="max-height:70vh; overflow:auto">
          <!-- Markdown shown as-is (no renderer dependency); pre-wrap keeps structure readable. -->
          <div style="white-space:pre-wrap; font-size:0.875rem; line-height:1.5">{{ modalContent }}</div>
        </div>
      </div>
    </div>
  </div>
</template>
