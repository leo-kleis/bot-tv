import { html, useState, useEffect, useRef, createPortal } from 'preact-setup';
import { apiGet, apiPost } from '/static/components/api.js';
import { getFocusableElements, trapFocus, setupInertIsolation } from '/static/lib/a11y.js';
import { sanitizeHttpUrl } from 'lib/utils';

export function StreamEditModal({ initialTitle = '', initialCategory = '', onClose, onSaved }) {
  const [title, setTitle] = useState(initialTitle);
  const [selectedCategory, setSelectedCategory] = useState(
    initialCategory ? { id: '', name: initialCategory } : null
  );

  // Estados del buscador reactivo con debounce (patrón FollowersFilterBar/FollowersTab)
  const [categoryInput, setCategoryInput] = useState('');
  const [categorySearch, setCategorySearch] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [searching, setSearching] = useState(false);
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);
  const [dropdownPos, setDropdownPos] = useState({ top: 0, left: 0, width: 0 });
  const [portalRoot, setPortalRoot] = useState(null);

  const [saving, setSaving] = useState(false);
  const [errorMsg, setErrorMsg] = useState(null);

  const categoryBoxRef = useRef(null);
  const modalRef = useRef(null);
  const dialogRef = useRef(null);
  const triggerRef = useRef(null);
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;

  // Cargar metadatos completos (portada box_art_url) si existe una categoría inicial
  useEffect(() => {
    if (!initialCategory || (selectedCategory && selectedCategory.box_art_url)) return;
    const controller = new AbortController();
    apiGet(`/api/categories/search?query=${encodeURIComponent(initialCategory)}`, {
      signal: controller.signal,
    })
      .then(res => {
        if (controller.signal.aborted) return;
        if (
          res &&
          res.ok &&
          Array.isArray(res.data?.categories) &&
          res.data.categories.length > 0
        ) {
          const match =
            res.data.categories.find(c => c.name.toLowerCase() === initialCategory.toLowerCase()) ||
            res.data.categories[0];
          setSelectedCategory({
            id: match.id,
            name: match.name,
            box_art_url: match.box_art_url,
          });
        }
      })
      .catch(() => {});
    return () => controller.abort();
  }, [initialCategory]);

  // Aislamiento inert, foco inicial y restauración de foco al desmontar
  useEffect(() => {
    triggerRef.current = document.activeElement;
    const restoreInert = setupInertIsolation(modalRef.current);

    const focusTimer = requestAnimationFrame(() => {
      const titleInput = document.getElementById('stream-title-input');
      if (titleInput) {
        titleInput.focus();
      } else if (dialogRef.current) {
        const first = getFocusableElements(dialogRef.current)[0];
        if (first) first.focus();
      }
    });

    return () => {
      cancelAnimationFrame(focusTimer);
      restoreInert();

      const prevEl = triggerRef.current;
      if (prevEl && typeof prevEl.focus === 'function' && document.body.contains(prevEl)) {
        prevEl.focus();
      }
    };
  }, []);

  // Manejador de tecla Esc, Tab (trap de foco) y clic fuera del dropdown
  useEffect(() => {
    function handleKeyDown(e) {
      if (e.key === 'Escape') {
        if (dropdownOpen) {
          setDropdownOpen(false);
        } else if (onCloseRef.current) {
          e.preventDefault();
          e.stopPropagation();
          onCloseRef.current();
        }
        return;
      }

      if (e.key === 'Tab') {
        trapFocus(dialogRef.current, e);
      }
    }

    function handleClickOutside(e) {
      const portalEl = document.getElementById('stream-category-portal');
      if (
        categoryBoxRef.current &&
        !categoryBoxRef.current.contains(e.target) &&
        (!portalEl || !portalEl.contains(e.target))
      ) {
        setDropdownOpen(false);
      }
    }

    window.addEventListener('keydown', handleKeyDown);
    document.addEventListener('mousedown', handleClickOutside);
    return () => {
      window.removeEventListener('keydown', handleKeyDown);
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [dropdownOpen]);

  // Calcular posición del dropdown flotante
  const updateDropdownPos = () => {
    if (!categoryBoxRef.current) return;
    const rect = categoryBoxRef.current.getBoundingClientRect();
    setDropdownPos({
      top: rect.bottom + 6,
      left: rect.left,
      width: rect.width,
    });
  };

  useEffect(() => {
    if (dropdownOpen && searchResults.length > 0) {
      updateDropdownPos();
      const handleScrollOrResize = () => updateDropdownPos();
      window.addEventListener('resize', handleScrollOrResize);
      window.addEventListener('scroll', handleScrollOrResize, true);
      return () => {
        window.removeEventListener('resize', handleScrollOrResize);
        window.removeEventListener('scroll', handleScrollOrResize, true);
      };
    }
  }, [dropdownOpen, searchResults]);

  useEffect(() => {
    if (!dropdownOpen || activeIndex < 0) return;
    const activeEl = document.getElementById(`stream-category-option-${activeIndex}`);
    if (activeEl && typeof activeEl.scrollIntoView === 'function') {
      activeEl.scrollIntoView({ block: 'nearest' });
    }
  }, [dropdownOpen, activeIndex]);

  // Debounce de búsqueda de categoría (500ms)
  useEffect(() => {
    const timer = setTimeout(() => {
      setCategorySearch(categoryInput);
    }, 500);
    return () => clearTimeout(timer);
  }, [categoryInput]);

  // Consulta de categorías contra la API de Twitch
  useEffect(() => {
    const query = categorySearch.trim();
    if (!query) {
      setSearchResults([]);
      setDropdownOpen(false);
      setActiveIndex(-1);
      return;
    }

    const controller = new AbortController();
    setSearching(true);
    setErrorMsg(null);

    apiGet(`/api/categories/search?query=${encodeURIComponent(query)}`, {
      signal: controller.signal,
    })
      .then(res => {
        if (controller.signal.aborted) return;
        setSearching(false);
        if (res && res.ok && Array.isArray(res.data?.categories)) {
          setSearchResults(res.data.categories);
          setDropdownOpen(res.data.categories.length > 0);
          setActiveIndex(-1);
        } else {
          setSearchResults([]);
          setDropdownOpen(false);
          setActiveIndex(-1);
        }
      })
      .catch(() => {
        if (controller.signal.aborted) return;
        setSearching(false);
        setSearchResults([]);
        setDropdownOpen(false);
        setActiveIndex(-1);
      });

    return () => {
      controller.abort();
    };
  }, [categorySearch]);

  function handleSelectCategory(cat) {
    setSelectedCategory({
      id: cat.id,
      name: cat.name,
      box_art_url: cat.box_art_url,
    });
    setCategoryInput('');
    setSearchResults([]);
    setDropdownOpen(false);
    setActiveIndex(-1);
  }

  function handleRemoveCategory() {
    setSelectedCategory(null);
  }

  function handleCategoryKeyDown(e) {
    if (!searchResults.length) {
      if (e.key === 'Escape' && dropdownOpen) {
        e.preventDefault();
        e.stopPropagation();
        setDropdownOpen(false);
        setActiveIndex(-1);
      }
      return;
    }

    if (e.key === 'ArrowDown') {
      e.preventDefault();
      if (!dropdownOpen) {
        setDropdownOpen(true);
        setActiveIndex(0);
      } else {
        setActiveIndex(prev => (prev + 1) % searchResults.length);
      }
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      if (!dropdownOpen) {
        setDropdownOpen(true);
        setActiveIndex(searchResults.length - 1);
      } else {
        setActiveIndex(prev => (prev <= 0 ? searchResults.length - 1 : prev - 1));
      }
    } else if (e.key === 'Enter') {
      if (dropdownOpen && activeIndex >= 0 && searchResults[activeIndex]) {
        e.preventDefault();
        handleSelectCategory(searchResults[activeIndex]);
      }
    } else if (e.key === 'Escape') {
      if (dropdownOpen) {
        e.preventDefault();
        e.stopPropagation();
        setDropdownOpen(false);
        setActiveIndex(-1);
      }
    }
  }

  // Crear y limpiar contenedor portal en document.body para el dropdown
  useEffect(() => {
    let el = document.getElementById('stream-category-portal');
    let created = false;
    if (!el) {
      el = document.createElement('div');
      el.id = 'stream-category-portal';
      document.body.appendChild(el);
      created = true;
    }
    setPortalRoot(el);
    return () => {
      if (created && el.parentNode) {
        el.parentNode.removeChild(el);
      }
    };
  }, []);

  async function handleSave() {
    setSaving(true);
    setErrorMsg(null);

    const body = {
      title: title.trim(),
    };
    if (selectedCategory && selectedCategory.id) {
      body.category_id = selectedCategory.id;
    }

    const res = await apiPost('/api/stream/update_info', body);
    setSaving(false);

    if (res && res.ok) {
      if (onSaved) {
        onSaved({
          title: title.trim(),
          category: selectedCategory ? selectedCategory.name : initialCategory,
        });
      }
      onClose();
    } else {
      setErrorMsg(res?.data?.error || res?.error || 'Error al actualizar el stream en Twitch.');
    }
  }

  const titleLength = title.length;
  const maxTitleLength = 140;

  const cardBoxArt = sanitizeHttpUrl(
    selectedCategory?.box_art_url
      ? selectedCategory.box_art_url.replace('{width}', '108').replace('{height}', '144')
      : ''
  );

  return html`
    <div
      class="stream-modal-backdrop"
      ref=${modalRef}
      onClick=${e => e.target === e.currentTarget && onClose && onClose()}
    >
      <div
        class="stream-modal-dialog"
        ref=${dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="stream-edit-modal-title"
        aria-describedby=${errorMsg ? 'stream-edit-modal-desc' : undefined}
      >
        <!-- Cabecera del Modal -->
        <div class="stream-modal-header">
          <div class="stream-modal-title">
            <span id="stream-edit-modal-title">Editar Información del Stream</span>
          </div>
          <button
            class="stream-modal-close-btn"
            onClick=${onClose}
            title="Cerrar modal"
            aria-label="Cerrar modal"
          >
            <i class="fa-solid fa-xmark"></i>
          </button>
        </div>

        <!-- Cuerpo del Modal -->
        <div class="stream-modal-body">
          ${
            errorMsg
              ? html`
                  <div id="stream-edit-modal-desc" class="stream-modal-alert" role="alert">
                    <i class="fa-solid fa-triangle-exclamation"></i>
                    <span>${errorMsg}</span>
                  </div>
                `
              : null
          }

          <!-- Campo Título -->
          <div class="stream-modal-field">
            <div class="stream-modal-label-row">
              <label class="stream-modal-label" for="stream-title-input"> Título del Stream </label>
              <span
                class="stream-modal-char-count ${titleLength > maxTitleLength ? 'exceeded' : ''}"
              >
                ${titleLength} / ${maxTitleLength}
              </span>
            </div>
            <input
              id="stream-title-input"
              type="text"
              class="stream-modal-input"
              maxlength=${maxTitleLength}
              placeholder="Escribe el título de tu transmisión..."
              value=${title}
              onInput=${e => setTitle(e.target.value)}
              disabled=${saving}
            />
          </div>

          <!-- Campo Categoría -->
          <div class="stream-modal-field category-field" ref=${categoryBoxRef}>
            <div class="stream-modal-label-row">
              <label class="stream-modal-label" for="stream-category-search"> Categoría </label>
            </div>

            <!-- Categoría Actualmente Seleccionada (Tarjeta Estilo Twitch) -->
            ${
              selectedCategory
                ? html`
                    <div class="twitch-category-card">
                      ${
                        cardBoxArt
                          ? html`<img
                              src=${cardBoxArt}
                              alt=${selectedCategory.name}
                              class="twitch-category-art"
                              loading="lazy"
                              onError=${e => {
                                e.target.style.display = 'none';
                              }}
                            />`
                          : html`<div class="twitch-category-art-placeholder">
                              <i class="fa-solid fa-gamepad"></i>
                            </div>`
                      }
                      <div class="twitch-category-info">
                        <span class="twitch-category-name">${selectedCategory.name}</span>
                      </div>
                      <button
                        type="button"
                        class="twitch-category-remove-btn"
                        onClick=${handleRemoveCategory}
                        title="Cambiar categoría"
                        aria-label="Quitar categoría seleccionada"
                        disabled=${saving}
                      >
                        <i class="fa-solid fa-xmark"></i>
                      </button>
                    </div>
                  `
                : null
            }

            <!-- Buscador de Categorías con Debounce -->
            <div class="category-search-box">
              <i class="fa-solid fa-magnifying-glass search-box-icon"></i>
              <input
                id="stream-category-search"
                type="text"
                role="combobox"
                aria-autocomplete="list"
                aria-expanded=${dropdownOpen && searchResults.length > 0}
                aria-controls="stream-category-listbox"
                aria-activedescendant=${
                  dropdownOpen && activeIndex >= 0
                    ? `stream-category-option-${activeIndex}`
                    : undefined
                }
                class="stream-modal-input category-search-input"
                placeholder=${
                  selectedCategory
                    ? 'Buscar otra categoría en Twitch...'
                    : 'Buscar categoría o juego en Twitch...'
                }
                value=${categoryInput}
                onInput=${e => setCategoryInput(e.target.value)}
                onKeyDown=${handleCategoryKeyDown}
                onFocus=${() => searchResults.length > 0 && setDropdownOpen(true)}
                disabled=${saving}
              />
              ${
                searching
                  ? html`<span class="search-box-spinner"
                      ><i class="fa-solid fa-spinner fa-spin"></i
                    ></span>`
                  : null
              }
            </div>
          </div>
        </div>

        <!-- Pie de Botones de Acción -->
        <div class="stream-modal-footer">
          <button
            type="button"
            class="btn btn-secondary stream-modal-btn"
            onClick=${onClose}
            disabled=${saving}
          >
            Cancelar
          </button>
          <button
            type="button"
            class="btn btn-primary stream-modal-btn"
            onClick=${handleSave}
            disabled=${saving || titleLength > maxTitleLength}
          >
            ${
              saving
                ? html`<i class="fa-solid fa-spinner fa-spin"></i> Guardando...`
                : html`<i class="fa-solid fa-check"></i> Guardar Cambios`
            }
          </button>
        </div>
      </div>

      ${
        dropdownOpen && searchResults.length > 0 && portalRoot
          ? createPortal(
              html`
                <div
                  id="stream-category-listbox"
                  role="listbox"
                  aria-label="Categorías disponibles"
                  class="category-dropdown-list"
                  style="position:fixed;top:${dropdownPos.top}px;left:${dropdownPos.left}px;width:${dropdownPos.width}px;z-index:var(--z-modal-dropdown);"
                >
                  ${searchResults.map((cat, idx) => {
                    const rawArt = cat.box_art_url
                      ? cat.box_art_url.replace('{width}', '52').replace('{height}', '72')
                      : '';
                    const boxArt = sanitizeHttpUrl(rawArt);
                    const isSelected = idx === activeIndex;
                    return html`
                      <div
                        key=${cat.id}
                        id="stream-category-option-${idx}"
                        role="option"
                        aria-selected=${isSelected}
                        class="category-dropdown-item ${isSelected ? 'active' : ''}"
                        onMouseEnter=${() => setActiveIndex(idx)}
                        onClick=${() => handleSelectCategory(cat)}
                      >
                        ${
                          boxArt
                            ? html`<img
                                src=${boxArt}
                                alt=${cat.name}
                                class="category-box-art"
                                loading="lazy"
                                onError=${e => {
                                  e.target.style.display = 'none';
                                }}
                              />`
                            : html`<div class="category-box-art-placeholder">
                                <i class="fa-solid fa-gamepad"></i>
                              </div>`
                        }
                        <span class="category-item-name">${cat.name}</span>
                      </div>
                    `;
                  })}
                </div>
              `,
              portalRoot
            )
          : null
      }
    </div>
  `;
}
