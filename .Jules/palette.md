## Keyboard Navigation & Focus States

When designing interactive elements like buttons, it is essential to ensure they are accessible via keyboard navigation.

- Use `:focus-visible` to provide clear focus indicators for users navigating via keyboard (like Tab). This avoids showing focus outlines on mouse clicks, maintaining a clean aesthetic for mouse users while ensuring accessibility for keyboard users.
- A standard outline like `outline: 2px solid var(--accent); outline-offset: 2px;` works well to make the focus state clearly visible.
