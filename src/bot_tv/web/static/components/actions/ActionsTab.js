import { h } from '/static/vendor/preact.module.js';
import htm from '/static/vendor/htm.module.js';
import { ClipSection } from '/static/components/actions/ClipSection.js';
import { UserSection } from '/static/components/actions/UserSection.js';
import { ModelSection } from '/static/components/actions/ModelSection.js';
import { DangerSection } from '/static/components/actions/DangerSection.js';

const html = htm.bind(h);

export function ActionsTab({ clips, dispatch }) {
  return html`
    <div class="panel actions-grid" id="actions-panel">
      <div class="actions-col">
        <${ClipSection} clips=${clips} />
        <${ModelSection} />
      </div>
      <div class="actions-col">
        <${UserSection} />
        <${DangerSection} dispatch=${dispatch} />
      </div>
    </div>
  `;
}
