import { h } from '/static/vendor/preact.module.js';
import htm from '/static/vendor/htm.module.js';
import { ClipSection } from '/static/components/actions/ClipSection.js';
import { UserSection } from '/static/components/actions/UserSection.js';
import { ModelSection } from '/static/components/actions/ModelSection.js';
import { DangerSection } from '/static/components/actions/DangerSection.js';

const html = htm.bind(h);

export function ActionsTab({ clips, dispatch }) {
  return html`
    <div class="panel" id="actions-panel">
      <${ClipSection} clips=${clips} />
      <${UserSection} />
      <${ModelSection} />
      <${DangerSection} dispatch=${dispatch} />
    </div>
  `;
}
