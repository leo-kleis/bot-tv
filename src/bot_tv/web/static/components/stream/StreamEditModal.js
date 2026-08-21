import { html, useState, useEffect, useRef, render } from 'preact-setup';
import { apiGet, apiPost } from '/static/components/api.js';

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
  const [dropdownPos, setDropdownPos] = useState({ top: 0, left: 0, width: 0 });

  const [saving, setSaving] = useState(false);
  const [errorMsg, setErrorMsg] = useState(null);

  const categoryBoxRef = useRef(null);

  // Cargar metadatos completos (portada box_art_url) si existe una categoría inicial
  useEffect(() => {
    if (initialCategory && (!selectedCategory || !selectedCategory.box_art_url)) {
      apiGet(`/api/categories/search?query=${encodeURIComponent(initialCategory)}`)
        .then(res => {
          if (
            res &&
            res.ok &&
            Array.isArray(res.data?.categories) &&
            res.data.categories.length > 0
          ) {
            const match =
              res.data.categories.find(
                c => c.name.toLowerCase() === initialCategory.toLowerCase()
              ) || res.data.categories[0];
            setSelectedCategory({
              id: match.id,
              name: match.name,
              box_art_url: match.box_art_url,
            });
          }
        })
        .catch(() => {});
    }
  }, [initialCategory]);

  // Manejador de tecla Esc y clic fuera del dropdown
  useEffect(() => {
    function handleKeyDown(e) {
      if (e.key === 'Escape') {
        if (dropdownOpen) {
          setDropdownOpen(false);
        } else {
          onClose();
        }
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
  }, [onClose, dropdownOpen]);

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
      return;
    }

    let active = true;
    setSearching(true);
    setErrorMsg(null);

    apiGet(`/api/categories/search?query=${encodeURIComponent(query)}`)
      .then(res => {
        if (!active) return;
        setSearching(false);
        if (res && res.ok && Array.isArray(res.data?.categories)) {
          setSearchResults(res.data.categories);
          setDropdownOpen(res.data.categories.length > 0);
        } else {
          setSearchResults([]);
          setDropdownOpen(false);
        }
      })
      .catch(() => {
        if (!active) return;
        setSearching(false);
        setSearchResults([]);
        setDropdownOpen(false);
      });

    return () => {
      active = false;
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
  }

  function handleRemoveCategory() {
    setSelectedCategory(null);
  }

  // Renderizar dropdown en portal a document.body para evitar recorte por scroll del modal
  useEffect(() => {
    let portalRoot = document.getElementById('stream-category-portal');
    if (!dropdownOpen || searchResults.length === 0) {
      if (portalRoot) {
        render(null, portalRoot);
      }
      return;
    }

    if (!portalRoot) {
      portalRoot = document.createElement('div');
      portalRoot.id = 'stream-category-portal';
      document.body.appendChild(portalRoot);
    }

    const dropdownContent = html`
      <div
        class="category-dropdown-list"
        style="position:fixed;top:${dropdownPos.top}px;left:${dropdownPos.left}px;width:${dropdownPos.width}px;z-index:var(--z-popover);"
      >
        ${searchResults.map(cat => {
          const boxArt = cat.box_art_url
            ? cat.box_art_url.replace('{width}', '52').replace('{height}', '72')
            : null;
          return html`
            <div
              key=${cat.id}
              class="category-dropdown-item"
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
    `;

    render(dropdownContent, portalRoot);

    return () => {
      if (portalRoot) {
        render(null, portalRoot);
      }
    };
  }, [dropdownOpen, searchResults, dropdownPos]);

  // Limpiar portal al desmontar
  useEffect(() => {
    return () => {
      const portalRoot = document.getElementById('stream-category-portal');
      if (portalRoot) {
        render(null, portalRoot);
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

  const cardBoxArt = selectedCategory?.box_art_url
    ? selectedCategory.box_art_url.replace('{width}', '108').replace('{height}', '144')
    : null;

  return html`
    <div class="stream-modal-backdrop" onClick=${e => e.target === e.currentTarget && onClose()}>
      <div class="stream-modal-dialog" role="dialog" aria-modal="true">
        <!-- Cabecera del Modal -->
        <div class="stream-modal-header">
          <div class="stream-modal-title">
            <span>Editar Información del Stream</span>
          </div>
          <button class="stream-modal-close-btn" onClick=${onClose} title="Cerrar modal">
            <i class="fa-solid fa-xmark"></i>
          </button>
        </div>

        <!-- Cuerpo del Modal -->
        <div class="stream-modal-body">
          ${
            errorMsg
              ? html`
                  <div class="stream-modal-alert">
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
              <label class="stream-modal-label"> Categoría </label>
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
                type="text"
                class="stream-modal-input category-search-input"
                placeholder=${
                  selectedCategory
                    ? 'Buscar otra categoría en Twitch...'
                    : 'Buscar categoría o juego en Twitch...'
                }
                value=${categoryInput}
                onInput=${e => setCategoryInput(e.target.value)}
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
    </div>
  `;
}
