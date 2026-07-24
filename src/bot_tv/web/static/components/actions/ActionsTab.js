import { html } from 'preact-setup';
import { ClipSection } from '/static/components/actions/ClipSection.js';
import { DangerSection } from '/static/components/actions/DangerSection.js';

export function ActionsTab({ clips, dispatch, streamOnline }) {
  return html`
    <div class="panel" id="actions-panel" style="width: 100%;">
      <${ClipSection} clips=${clips} streamOnline=${streamOnline} />
      <${DangerSection} dispatch=${dispatch} />
    </div>
  `;
}
