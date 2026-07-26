import { html } from 'preact-setup';
import { DangerSection } from '/static/components/actions/DangerSection.js';

export function ActionsTab({ dispatch }) {
  return html`
    <div class="panel" id="actions-panel" style="width: 100%;">
      <${DangerSection} dispatch=${dispatch} />
    </div>
  `;
}
