# FlipperHelper

An iOS app for people who buy items at markets, car boot sales, and flea markets to resell for profit. Track every purchase with a photo, manage listings across 14 selling platforms, record sales, monitor expenses, and see your real profit — all offline-first with optional Google Drive sync.

**Built with Swift & SwiftUI | iOS 17+ | Offline-First | No backend required**

---

## Why FlipperHelper?

If you flip items for profit — buying at car boot sales, charity shops, flea markets, or anywhere else — you know the pain of tracking everything. What did you pay? Where did you list it? Did it sell? What's your actual profit after entry fees and petrol?

FlipperHelper solves this. Snap a photo at the market, log the price, and the app tracks everything from purchase to sale. No spreadsheet juggling, no forgetting what you paid, no guessing your profit.

---

## Features

### Core
- **Purchase Tracking** — Snap photos, log prices, assign markets and sellers. Sequential IDs (FH-1, FH-2, ...) for easy reference
- **Custom Markets** — Add your own markets with optional GPS coordinates. The app auto-suggests the right market when you're nearby (configurable radius, default 5 km)
- **Seller Tracking** — Track who you bought from at each market
- **Item Titles** — Optional descriptions for each item

### Listing Management
- **14 Selling Platforms** — eBay, Facebook Marketplace, Vinted, Depop, Poshmark, Mercari, OfferUp, Craigslist, ThredUp, Etsy, Gumtree, Shpock, Preloved, Nextdoor
- **Platform Selection** — Enable only the platforms you use in Settings
- **Per-Item Tracking** — Toggle listings per item, track listing dates
- **Smart Tabs** — Items flow through New → Listed → Sold tabs automatically
- **5-Second Grace Period** — Newly listed items stay in the "New" tab for 5 seconds so you can undo accidental taps

### Sales
- **Record Sales** — Sale price, platform sold on, payment method (cash/card)
- **Profit Calculation** — Automatic per-item profit (sale price minus purchase price)
- **Days to Sell** — Tracks how long each item took to sell

### Expenses
- **Entry Fees** — Track market entry fees linked to specific markets and dates
- **Transport Costs** — Car (gas, service, parking), bus, train, taxi, van, bike rental
- **Per-Market Breakdown** — See how much you spend getting to each market

### Financial Analytics (Money Flow)
- **Net Profit** — Revenue minus cost of goods minus all expenses
- **Time Periods** — Week, month, 3 months, year, or all-time views
- **Monthly Profit Chart** — Visual bar chart of profit by month (uses Swift Charts)
- **Inventory Value** — Total value of unsold stock
- **Expense Breakdown** — Entry fees vs transport costs
- **Sold Items List** — See every sale with individual profit/loss

### Notifications
- **Listing Reminders** — Configurable push notifications to remind you about unlisted items
- **Day Selection** — Choose which days (Mon–Sun) to get reminded
- **Time Selection** — Set your preferred reminder time
- **Smart Content** — Shows count and age: *"You have 5 items not listed. Oldest: 12 days ago"*

### Settings & Customization
- **Multi-Currency** — USD ($), EUR (€), GBP (£)
- **Platform Management** — Enable/disable selling platforms. Disabling removes listings from all items
- **Data Statistics** — See counts of items, markets, sellers, expenses
- **App Version Display** — Version and build number shown in settings

### Data & Sync
- **Fully Offline** — Everything works without internet. No account required
- **Google Drive Sync** — Optional. Photos sync to Drive, data exports as Google Sheets
- **Background Sync** — Photos upload in the background via BGTaskScheduler
- **CSV Export** — Items and expenses export as CSV, auto-converted to Google Sheets
- **Backup & Restore** — Full ZIP backup of all JSON data + photos. Restore on any device
- **Soft Deletes** — Deleted items are marked, not destroyed, for data safety

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                          SwiftUI Views                          │
│  MoneyFlowView │ ItemsListView │ EntryFeesView │ SettingsView   │
└─────────────────────────────┬───────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                         ViewModels                              │
│                  AppViewModel │ SettingsViewModel                │
└─────────────────────────────┬───────────────────────────────────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────────────┐
│    DataStore    │ │ SyncQueueService│ │     ExportService       │
│    (actor)      │ │  (images only)  │ │   (CSV → Sheets)        │
└────────┬────────┘ └────────┬────────┘ └───────────┬─────────────┘
         │                   │                      │
         │                   ▼                      ▼
         │          ┌─────────────────────────────────────────────┐
         │          │            GoogleDriveService               │
         │          │  (image upload + CSV to Sheets export)      │
         │          └─────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Local JSON Files                             │
│  items.json │ markets.json │ sellers.json │ expenses.json │...  │
└─────────────────────────────────────────────────────────────────┘
```

### Key Design Decisions

1. **Offline-First** — Items default to "synced" status (synced to local storage). Google Drive is purely optional
2. **No Sheets API** — Uses only Google Drive API (`drive.file` scope) for better privacy. CSV files are uploaded with MIME type conversion so Google auto-converts them to Sheets
3. **Actor-Based DataStore** — Thread-safe data access using Swift actors. All JSON read/write goes through a single actor
4. **Image-Only Sync Queue** — Background sync handles only photo uploads. Data export is manual and intentional
5. **No CoreData/SQLite** — Plain JSON files in the Documents directory. Simple, portable, human-readable, easy to back up
6. **Soft Deletes** — All entities use a `deleted: Bool` flag rather than actual deletion
7. **BGTaskScheduler** — Background photo uploads continue even when the app is suspended

---

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Language | Swift |
| UI | SwiftUI |
| Minimum iOS | 17.0 |
| Charts | Swift Charts |
| Storage | Local JSON files |
| Auth | Google OAuth 2.0 |
| Cloud | Google Drive API (`drive.file` scope) |
| Background | BGTaskScheduler |
| Location | CoreLocation |
| Notifications | UserNotifications |
| Camera | UIImagePickerController / PhotosUI |
| Build | Xcode 15+, Taskfile |
| CI/CD | GitHub Actions |
| Distribution | TestFlight |
| Device Deploy | ios-deploy |

---

## Google Integration

### Simplified Approach

Unlike traditional inventory apps that require constant API access, FlipperHelper uses a minimal approach:

- **Scope**: Only `drive.file` (access to files created by the app) + `email`
- **No Sheets API**: Exports CSV files that Google automatically converts to Sheets
- **Folder Structure**: `FlipperHelper_App/images/` on Google Drive
- **Manual Export**: User decides when to export data — no automatic data sync

### Export Flow

```
User taps "Export Items"
        │
        ▼
ExportService.exportItems()
        │
        ├── Sync all pending images first
        │
        ├── Generate CSV from local data
        │
        └── GoogleDriveService.uploadCSVAsSpreadsheet()
                │
                ├── If exists: PATCH update (URL stays same)
                │
                └── If new: Create with mimeType conversion
```

**Items CSV columns**: ID, Photo URL, Price, Purchase Date, Market, Seller, [Platform Listed + Date for each enabled platform], Sold, Sold Date, Sold Price, Sold Platform, Payment Method, Profit, Days to Sell, Title

**Expenses CSV columns**: Type, Subtype, Date, Amount, Market, Memo

### Image Sync

Images sync to Google Drive with smart verification:

1. Gets all items with local photos
2. For items with existing Drive ID → sends GET to verify it still exists
3. If not found on Drive → clears stale ID and re-uploads
4. New items without Drive ID → uploads immediately
5. Background sync via BGTaskScheduler continues when app is suspended

---

## Data Models

### Item

```swift
struct Item: Identifiable, Codable {
    let id: UUID
    var localId: Int                    // Sequential ID (FH-1, FH-2, ...)
    var price: Double                   // Purchase price
    var title: String?                  // Optional description
    var marketId: UUID?                 // Link to Market
    var sellerId: UUID?                 // Link to Seller
    var photoLocalPath: String?         // Local image path
    var photoGoogleDriveId: String?     // Google Drive file ID
    var platformListings: [PlatformListing]  // Where listed + when
    var isSold: Bool
    var soldAt: Date?
    var soldPrice: Double?
    var soldPlatform: SoldPlatform?     // eBay, Facebook, etc.
    var paymentMethod: PaymentMethod?   // Cash or Card
    var deleted: Bool                   // Soft delete
}
```

### Market

```swift
struct Market: Identifiable, Codable {
    let id: UUID
    var name: String
    var latitude: Double?
    var longitude: Double?
    var radiusKm: Double        // Detection radius (default 5.0 km)
    var deleted: Bool
}
```

### Expenses

```swift
struct EntryFee: Identifiable, Codable {
    var amount: Double
    var date: Date
    var marketId: UUID          // Linked to a market
}

struct TransportExpense: Identifiable, Codable {
    var transportType: TransportType       // car, bus, train, taxi, van, bikeRent
    var carSubcategory: CarExpenseSubcategory?  // gas, service, parking
    var amount: Double
    var date: Date
    var memo: String?
    var marketId: UUID?
}
```

---

## Listing Platforms

Users enable/disable platforms in Settings. All 14 supported platforms:

| Platform | Platform | Platform |
|----------|----------|----------|
| eBay | Facebook Marketplace | Vinted |
| Depop | Poshmark | Mercari |
| OfferUp | Craigslist | ThredUp |
| Etsy | Gumtree | Shpock |
| Preloved | Nextdoor | |

Each platform can be toggled per-item. When a platform is disabled globally, all existing listings on that platform are removed from items.

---

## Project Structure

```
FlipperHelper/
├── FlipperHelperApp.swift          # Entry point, BGTask registration
├── Models/
│   ├── Item.swift                  # Core item with listings, sales, sync
│   ├── Market.swift                # Markets with geolocation
│   ├── Seller.swift                # Sellers
│   ├── EntryFee.swift              # Market entry fees
│   ├── TransportExpense.swift      # Transport costs (6 types)
│   ├── AppSettings.swift           # All app configuration
│   └── SyncQueueItem.swift         # Image upload queue entries
├── Views/
│   ├── MainTabView.swift           # Tab navigation (4 tabs)
│   ├── HomeView.swift              # Dashboard with stats
│   ├── MoneyFlowView.swift         # Financial analytics + charts
│   ├── ItemsListView.swift         # Items with New/Listed/Sold tabs
│   ├── AddItemView.swift           # Camera/photo + item creation
│   ├── EntryFeesView.swift         # Entry fees + transport expenses
│   ├── SettingsView.swift          # All settings + Google sync
│   ├── CameraView.swift            # Camera interface
│   ├── CachedImageView.swift       # Lazy-loaded cached images
│   ├── PhotoPickerView.swift       # Photo library picker
│   ├── RecentPhotosPicker.swift    # Recent photos quick picker
│   ├── PlatformSelectionView.swift # Platform toggle UI
│   ├── Items/
│   │   ├── ItemDetailSheet.swift   # Item detail + edit
│   │   └── SoldItemSheet.swift     # Mark as sold flow
│   └── Settings/
│       ├── EditMarketView.swift    # Edit market details
│       ├── EditSellerView.swift    # Edit seller details
│       └── SyncQueueView.swift     # View pending uploads
├── ViewModels/
│   ├── AppViewModel.swift          # Main app state
│   ├── ItemsListViewModel.swift    # Items list logic
│   └── SettingsViewModel.swift     # Settings logic
├── Services/
│   ├── DataStore.swift             # Actor — local JSON persistence (1200+ lines)
│   ├── GoogleAuthService.swift     # OAuth 2.0 flow
│   ├── GoogleDriveService.swift    # Drive API (upload, verify, delete)
│   ├── SyncQueueService.swift      # Background image upload queue
│   ├── BackgroundSyncService.swift # BGTaskScheduler integration
│   ├── BackgroundUploadService.swift # Upload task management
│   ├── ExportService.swift         # CSV generation + Sheets export
│   ├── LocationService.swift       # Geolocation for market auto-suggest
│   ├── NotificationService.swift   # Listing reminder notifications
│   ├── ImageCache.swift            # Thumbnail caching
│   ├── NetworkMonitor.swift        # Connectivity detection
│   ├── MigrationService.swift      # Data schema migrations
│   ├── HapticManager.swift         # Haptic feedback
│   └── LocalizationManager.swift   # UI strings
├── Helpers/
│   ├── PriceFormatter.swift        # Currency formatting
│   └── SKUFormatter.swift          # FH-XXX ID formatting
└── Assets.xcassets/                # App icon + platform logos
```

---

## Data Storage

All data stored locally as JSON in the app's Documents directory:

| File | Contents |
|------|----------|
| `items.json` | All items (purchases, listings, sales) |
| `markets.json` | Custom markets with geolocation |
| `sellers.json` | Sellers |
| `entryFees.json` | Market entry fees |
| `transportExpenses.json` | Transport costs |
| `settings.json` | App configuration + Google tokens |
| `syncQueue.json` | Pending image uploads |
| `Images/` | Local item photos (resized on save) |

### Backup & Restore

Full backup creates a ZIP archive containing all JSON files and the Images folder. Can be shared via iOS share sheet and restored on the same or a different device.

---

## Building & Running

### Requirements

- Xcode 15+
- iOS 17.0+
- macOS Sonoma+ (for development)
- [Task](https://taskfile.dev/) (optional, for Taskfile commands)
- [ios-deploy](https://github.com/ios-control/ios-deploy) (optional, for device deployment)

### Setup

```bash
# Clone
git clone https://github.com/OPrudnikov/flipper_helper.git
cd flipper_helper

# Open in Xcode
task open
# or: open FlipperHelper/FlipperHelper.xcodeproj

# Build (debug, for simulator)
task build

# Run tests
task test

# Build + test
task check
```

### Deploy to Device

```bash
# Build and install on connected iPhone via ios-deploy
task deploy
```

### Version Management

```bash
# Set app version
task bump-version VERSION=1.2.0
```

### Release to TestFlight

```bash
# Full release: archive + sign + upload to TestFlight
task release VERSION=1.2.0
```

Requires environment variables for code signing (see `.env.sample`):
- `CERTIFICATES_P12` — Base64-encoded signing certificate
- `CERTIFICATES_PASSWORD` — Certificate password
- `PROVISIONING_PROFILE` — Base64-encoded provisioning profile
- `ASC_KEY_ID`, `ASC_ISSUER_ID`, `ASC_API_KEY` — App Store Connect API credentials
- `TEAM_ID` — Apple Developer Team ID

### CI/CD

GitHub Actions workflows handle:
- **Build & Test** — On every push, builds the project and runs unit tests
- **Release** — Triggered by version tags, archives and uploads to TestFlight

---

## Common Workflows

### Adding a New Item

1. Open the "New Item" tab
2. Take a photo or pick from library
3. Enter purchase price
4. Select market (auto-suggested if you're nearby)
5. Optionally select seller and add a title
6. Tap "Save"

Photo is automatically queued for Google Drive upload (if connected).

### Listing an Item

1. Find item in the items list (New tab)
2. Tap platform buttons (eBay, Vinted, etc.)
3. Item moves to "Listed" tab after 5-second grace period

### Marking as Sold

1. Tap "Sold" on an item
2. Select where it sold (platform)
3. Choose payment method (cash/card)
4. Enter sale price
5. Confirm — item moves to "Sold" tab

### Tracking Expenses

1. Go to Expenses tab
2. Add entry fee (amount + market + date) or transport expense (type + amount + date)
3. Expenses are factored into Money Flow net profit calculations

### Exporting to Google Sheets

1. Connect Google account in Settings
2. Tap "Export Items" or "Export Expenses"
3. CSV is generated and uploaded to Google Drive as a Spreadsheet
4. Tap the link to open in browser — URL stays the same on subsequent exports

---

## Development Story

FlipperHelper was built from scratch in **12 days** (Feb 20 – Mar 3, 2026) as a real tool for real flipping. Here's the full development timeline:

### Day 1 — Feb 20: The Beginning
- **Initial commit** — Project created, basic structure laid out
- **First working version** — Core item tracking with photo capture, price logging
- **Sync queue** — Image upload queue to Google Drive implemented from day one

### Day 2 — Feb 21: Making It Useful
- **Earnings tracking** — Added financial calculations and profit display
- **Localization** — Multi-language support added (initially English + Russian)
- **Tests & fixes** — First unit tests, early bug fixes
- **README** — First documentation

### Days 3–4 — Feb 24: The Big Feature Push
- **Backup system** — Full data backup and restore via ZIP archives
- **Image resizing** — Photos compressed on save to reduce storage
- **Platform selection** — Users choose which selling platforms they use (the 14-platform system)
- **Google made optional** — App works fully without Google account
- **Comprehensive tests** — Model tests, export tests, helper tests, migration tests, DataStore tests
- **CI/CD pipeline** — GitHub Actions for build and test on every push
- **Platform toggle bug fixes** — Enable/disable dialogs, per-item platform tracking
- **UI polish** — Keyboard handling, button improvements, entry fee date translation
- **Settings formatting** — Clean settings screen layout
- **More localization** — Extended translations throughout the app
- **Release workflow** — Automated TestFlight uploads triggered by git tags

### Day 5 — Feb 25: Documentation
- **README updates** — Comprehensive documentation of architecture and features

### Day 6 — Feb 26: Going to Production
- **Distribution setup** — Code signing, provisioning profiles, TestFlight pipeline
- **Asset catalog fixes** — Fixed all xcassets Contents.json files
- **Security cleanup** — Removed accidentally committed certificates from repo
- **Offline-first tests** — Updated test suite for offline-first sync behavior
- **CI signing fixes** — Multiple iterations to get manual code signing working in CI (certificate import, provisioning profiles, build settings)
- **TestFlight upload** — Automated upload via `xcrun altool`
- **Version from git tags** — App version set automatically from git tag
- **Export compliance** — Added compliance metadata for App Store
- **Legacy data import** — Migration path from older data formats
- **Photo picker fix** — Fixed photo selection flow
- **Platform & payment editing** — Change sold platform and payment method after the fact
- **English-first** — Switched primary language to English

### Day 7 — Feb 27: Polish & UX
- **Better Google buttons** — Improved sync UI
- **Tap-to-add expenses** — Streamlined expense entry
- **Notification settings** — Configurable listing reminder days and times
- **Dropped Russian** — Simplified to English-only
- **Lazy image loading** — Performance improvement for large item lists
- **Days to sell** — Simplified calculation and display
- **Haptic feedback** — Tactile responses throughout the app
- **Money Flow redesign** — New financial dashboard with charts

### Day 8 — Feb 28: Simplification
- **Removed Spreadsheets API dependency** — Switched to CSV-upload-as-Sheets approach (simpler, fewer permissions)
- **New Google sync buttons** — Cleaner sync UI
- **New app logo** — Fresh branding
- **Taskfile** — Added task runner for build, test, deploy commands
- **Environment config** — `.env` file for secrets management

### Day 9 — Mar 1: Background Sync
- **BackgroundSyncService** — Photos upload even when the app is in the background using BGTaskScheduler

### Day 10 — Mar 2: Google Overhaul
- **New Google client** — Rebuilt Google Drive integration
- **Token persistence** — Google auth tokens saved and restored across app launches

### Day 11 — Mar 3: Refinement
- **Background & delete fixes** — Fixed background sync edge cases and data deletion
- **Currency selection** — Added USD/EUR/GBP currency support
- **5-second listing timer** — Grace period to prevent accidental tab switches
- **Tab behavior fix** — Items no longer jump to Sold tab unexpectedly
- **Big refactoring** — Major codebase cleanup and restructuring
- **Dropped old queue UI** — Removed legacy sync queue display from main view
- **Offline-first architecture** — Final move to fully offline-first: items are "synced" to local storage by default, Google Drive is purely optional

---

## Stats

- **~11,300 lines** of Swift code
- **45+ source files** across Models, Views, ViewModels, Services, Helpers
- **14 selling platforms** supported
- **6 transport types** with car subcategories
- **5 test files** covering models, exports, helpers, migrations, and data store
- **12 days** from first commit to production-ready app

---

## License

MIT License — see LICENSE file.
