# Frontend Architecture Documentation

## 📁 Modular File Structure

The frontend has been refactored from a monolithic 1,107-line `app.js` into a clean, maintainable modular architecture with **13 focused files** (~1,575 lines total with documentation).

### Directory Structure

```
frontend/
├── scripts/
│   ├── config.js           (979 bytes)  - Configuration constants
│   ├── dom.js              (2.0 KB)     - DOM element references
│   ├── state.js            (1.0 KB)     - Application state management
│   ├── ui.js               (3.5 KB)     - UI utilities and helpers
│   ├── api.js              (2.1 KB)     - API communication layer
│   ├── events.js           (2.1 KB)     - Event listener bindings
│   ├── app.js              (661 bytes)  - Main initialization
│   └── managers/
│       ├── status.js       (428 bytes)  - Status refresh logic
│       ├── content.js      (1.2 KB)     - Content display coordination
│       ├── playlist.js     (5.2 KB)     - Playlist CRUD operations
│       ├── image.js        (3.2 KB)     - Image management
│       ├── video.js        (5.2 KB)     - Video download & management
│       └── playback.js     (1.2 KB)     - Slideshow playback control
├── index.html
├── style.css
├── app_monolithic.js       (backup - original refactored version)
└── app_old.js             (backup - original pre-refactoring version)
```

## 🎯 Module Responsibilities

### Core Modules (Foundational)

#### 1. **config.js** - Configuration & Constants

- `CONFIG` - Application-wide configuration (intervals, timeouts)
- `CONTENT_TYPES` - Content type definitions (image/video)
- `PLAYLIST_TYPE_CONFIG` - Type-specific display configuration
- `TOAST_TYPES` - Toast notification types

**No dependencies** - Pure configuration

#### 2. **dom.js** - DOM Element References

- Centralized access to all DOM elements
- Button references
- Input field references
- Container references
- Modal references
- Status element references

**Dependencies:** None (requires DOM to be ready)

#### 3. **state.js** - Application State Management

- `AppState` - Centralized application state
- Selected playlist tracking
- Current status storage
- Polling interval management

**Dependencies:** `CONFIG`

#### 4. **ui.js** - UI Utilities

- Loading overlay control
- Toast notifications
- Status display updates
- Progress bar management
- HTML escaping
- Duration formatting

**Dependencies:** `DOM`, `CONFIG`, `TOAST_TYPES`, `AppState`, `CONTENT_TYPES`

#### 5. **api.js** - API Communication

- Generic API call wrapper
- Status endpoints
- Playlist endpoints
- Image endpoints
- Video endpoints
- Playback control endpoints

**Dependencies:** `UI`, `TOAST_TYPES`

### Manager Modules (Business Logic)

#### 6. **managers/status.js** - Status Manager

- Refresh status from server
- Auto-refresh initialization
- Status display coordination

**Dependencies:** `API`, `AppState`, `UI`, `CONFIG`

**Size:** Smallest manager (428 bytes)
**Purpose:** Simple status polling and display

#### 7. **managers/content.js** - Content Manager

- Content section show/hide
- Coordinates image/video display
- Empty state rendering
- Type-specific button visibility

**Dependencies:** `DOM`, `UI`, `CONTENT_TYPES`, `PLAYLIST_TYPE_CONFIG`, `VideoManager`, `ImageManager`

**Size:** 1.2 KB
**Purpose:** Bridge between playlists and content display

#### 8. **managers/playlist.js** - Playlist Manager

- Load and display playlists
- Create playlist modal
- Playlist card generation
- Playlist selection
- CRUD operations

**Dependencies:** `API`, `DOM`, `UI`, `AppState`, `CONTENT_TYPES`, `PLAYLIST_TYPE_CONFIG`, `ContentManager`

**Size:** 5.2 KB (largest manager)
**Purpose:** Complete playlist lifecycle management

#### 9. **managers/image.js** - Image Manager

- Load playlist images
- Display image cards
- Image upload handling
- Multi-file upload
- Image deletion

**Dependencies:** `API`, `DOM`, `UI`, `AppState`, `ContentManager`, `PlaylistManager`, `CONTENT_TYPES`

**Size:** 3.2 KB
**Purpose:** Image-specific operations

#### 10. **managers/video.js** - Video Manager

- Load playlist videos
- Display video cards
- YouTube download modal
- Download progress polling
- Video deletion

**Dependencies:** `API`, `DOM`, `UI`, `AppState`, `ContentManager`, `PlaylistManager`, `CONTENT_TYPES`, `PLAYLIST_TYPE_CONFIG`, `CONFIG`

**Size:** 5.2 KB (tied for largest)
**Purpose:** Video download and management with progress tracking

#### 11. **managers/playback.js** - Playback Control

- Start slideshow playback
- Stop slideshow playback
- Status refresh coordination

**Dependencies:** `API`, `UI`, `AppState`, `StatusManager`, `PlaylistManager`, `TOAST_TYPES`

**Size:** 1.2 KB
**Purpose:** Simple start/stop control

### Integration Modules

#### 12. **events.js** - Event Listeners

- Binds all UI events to managers
- Playback control events
- Playlist control events
- Content control events
- Modal interaction events
- Keyboard shortcuts

**Dependencies:** All managers + `DOM`

**Size:** 2.1 KB
**Purpose:** Event binding coordination layer

#### 13. **app.js** - Main Entry Point

- DOMContentLoaded initialization
- Event listener initialization
- Initial data load
- Auto-refresh startup
- CSS animation injection

**Dependencies:** `EventListeners`, `StatusManager`, `PlaylistManager`

**Size:** 661 bytes (smallest file)
**Purpose:** Application bootstrap

## 🔄 Loading Order

Scripts are loaded in dependency order in `index.html`:

```html
<!-- Core modules -->
<script src="/frontend/scripts/config.js"></script>
<script src="/frontend/scripts/dom.js"></script>
<script src="/frontend/scripts/state.js"></script>
<script src="/frontend/scripts/ui.js"></script>
<script src="/frontend/scripts/api.js"></script>

<!-- Manager modules -->
<script src="/frontend/scripts/managers/status.js"></script>
<script src="/frontend/scripts/managers/content.js"></script>
<script src="/frontend/scripts/managers/playlist.js"></script>
<script src="/frontend/scripts/managers/image.js"></script>
<script src="/frontend/scripts/managers/video.js"></script>
<script src="/frontend/scripts/managers/playback.js"></script>

<!-- Event handlers and initialization -->
<script src="/frontend/scripts/events.js"></script>
<script src="/frontend/scripts/app.js"></script>
```

**Critical:** This order ensures all dependencies are available before dependent modules load.

## ✅ Benefits of This Architecture

### Maintainability

- **Single Responsibility:** Each module has one clear purpose
- **Small Files:** Largest file is 5.2 KB (vs. 30 KB monolithic)
- **Easy Navigation:** Clear file names indicate content
- **Isolated Changes:** Modifications don't affect unrelated code

### Scalability

- **Add Features:** New managers can be added without touching existing code
- **Extend Functionality:** Each manager can grow independently
- **Parallel Development:** Multiple developers can work on different managers

### Testability

- **Unit Testing:** Each module can be tested in isolation
- **Mock Dependencies:** Easy to mock API, UI, etc.
- **Clear Interfaces:** Module boundaries make testing obvious

### Readability

- **Clear Dependencies:** Each module declares what it needs
- **Logical Grouping:** Related functions stay together
- **JSDoc Comments:** Every function is documented

### Debugging

- **Error Isolation:** Problems are confined to specific modules
- **Stack Traces:** Clear file names in browser console
- **Module Boundaries:** Easy to identify problem areas

### Performance

- **No Bundle Required:** Direct script loading works fine
- **Browser Caching:** Unchanged modules stay cached
- **Progressive Enhancement:** Can load modules conditionally if needed

## 🔧 Common Development Tasks

### Adding a New Feature

**Example: Add a new content type (e.g., "audio")**

1. Update `config.js` → Add to `CONTENT_TYPES` and `PLAYLIST_TYPE_CONFIG`
2. Create `scripts/managers/audio.js` → Similar to `image.js`/`video.js`
3. Update `content.js` → Add audio case
4. Update `playlist.js` → Handle audio playlists
5. Update `events.js` → Add audio-specific events
6. Update `index.html` → Add new script tag

**Impact:** 5-6 files, no changes to unrelated managers

### Fixing a Bug

**Example: Fix video download progress display**

1. Identify: Bug is in progress polling
2. Open: `scripts/managers/video.js`
3. Locate: `pollStatus()` method
4. Fix: Update progress calculation
5. Test: No other files need changes

**Impact:** 1 file, isolated change

### Refactoring

**Example: Change API response format**

1. Update `api.js` → Modify endpoint methods
2. Update affected managers (e.g., `playlist.js`, `image.js`)
3. No changes to UI, DOM, State, Config modules

**Impact:** API layer + dependent managers only

## 📦 Backup Files

- **`app_monolithic.js`** - The 1,107-line refactored monolithic version (previous iteration)
- **`app_old.js`** - The original 807-line procedural version (initial state)

Both are preserved for reference or rollback if needed.

## 🚀 Next Steps

### Potential Improvements

1. **ES6 Modules:** Convert to ES6 modules with `import`/`export`
   - Requires build step or `type="module"` in script tags
   - Better dependency management
   - Tree-shaking support

2. **TypeScript:** Add type safety
   - Better IDE support
   - Catch errors at compile time
   - Self-documenting code

3. **Testing:** Add unit tests
   - Jest for unit tests
   - Playwright for E2E tests
   - Coverage reporting

4. **Build System:** Add bundler
   - Webpack/Vite for bundling
   - Code splitting
   - Minification

5. **State Management:** Consider formal state library
   - Redux/Zustand for complex state
   - Better state tracking
   - Time-travel debugging

### When to Keep Current Architecture

The current architecture is **perfect for:**

- ✅ Small to medium projects
- ✅ Raspberry Pi deployment (no build step needed)
- ✅ Direct browser execution
- ✅ Simple dependency tree
- ✅ Fast iteration cycles
- ✅ No external dependencies

### When to Upgrade

Consider upgrading when:

- ❌ Project grows beyond 20+ modules
- ❌ Multiple developers need better dependency management
- ❌ Need advanced tooling (hot reload, etc.)
- ❌ TypeScript safety becomes critical
- ❌ Build optimization becomes necessary

## 📊 Metrics

| Metric                | Before (Monolithic)                  | After (Modular)          |
| --------------------- | ------------------------------------ | ------------------------ |
| **Files**             | 1 file                               | 13 files                 |
| **Largest File**      | 1,107 lines (30 KB)                  | 202 lines (5.2 KB)       |
| **Smallest Module**   | N/A                                  | 16 lines (428 bytes)     |
| **Average File Size** | 30 KB                                | 2.0 KB                   |
| **Module Coupling**   | High (everything interconnected)     | Low (clear dependencies) |
| **Test Coverage**     | Hard to test                         | Easy to test             |
| **Maintenance**       | Difficult (find code in 1,107 lines) | Easy (clear file names)  |

## 🎓 Learning Resources

- **Module Pattern:** [MDN - Module Pattern](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Guide/Modules)
- **Separation of Concerns:** [Wikipedia](https://en.wikipedia.org/wiki/Separation_of_concerns)
- **Single Responsibility Principle:** [SOLID Principles](https://en.wikipedia.org/wiki/Single-responsibility_principle)

---

**Last Updated:** May 4, 2026
**Version:** 2.0 (Modular Architecture)
