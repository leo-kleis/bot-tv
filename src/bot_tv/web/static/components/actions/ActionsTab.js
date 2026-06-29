import { html } from 'preact-setup';
import { ClipSection } from '/static/components/actions/ClipSection.js';
import { ModelSection } from '/static/components/actions/ModelSection.js';
import { DangerSection } from '/static/components/actions/DangerSection.js';

export function ActionsTab({ clips, dispatch, streamOnline }) {
  return html`
    <div class="panel two-col-grid" id="actions-panel">
      <div class="two-col">
        <${ClipSection} clips=${clips} streamOnline=${streamOnline} />
        <${ModelSection} />
      </div>
      <div class="two-col">
        <${DangerSection} dispatch=${dispatch} />
      </div>
    </div>
  `;
}
