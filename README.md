# CAATmaster PySide 6

Professional Continuous Audit Analytics Tool - Desktop Application

## Overview

CAATmaster is a native desktop application for audit professionals, ported from the web-based procaat application. It provides sophisticated data analysis capabilities without requiring coding knowledge.

## Features

- **Data Import**: Load data from CSV, Excel, JSON, and Parquet files
- **Data Grid**: View and explore large datasets with a performant Qt table widget
- **Data Transformations**: Apply common transformations (uppercase, trim, round, filter, etc.)
- **ML Analytics**: Anomaly detection, classification, and risk scoring
- **AI Integration**: Optional AI features for column generation and sentiment analysis
- **Project Management**: Organize work into audit projects
- **Session Management**: Save and restore analysis sessions
- **SQLite Database**: Embedded database for maximum portability
- **Portable Distribution**: No installation required - just extract and run

## Technology Stack

| Component | Technology |
|-----------|-----------|
| GUI Framework | PySide 6 (Qt 6) |
| Data Processing | Polars 1.0+ |
| Database | SQLite (via SQLAlchemy 2.0) |
| ML/AI | scikit-learn, optional OpenAI/Anthropic |
| Build Tools | PyInstaller, AppImageKit (Linux) |
| Build Outputs | Portable dir, Single .exe (Win), AppImage (Linux) |

## Project Structure

```
caatmaster_pyside/
├── main.py                 # Application entry point
├── requirements.txt        # Python dependencies
├── build.py               # Universal build script (auto-detects platform)
├── build_windows.py       # Windows build (portable or single .exe)
├── build_linux.py         # Linux build (portable directory)
├── build_appimage.py      # Linux AppImage build (single file)
├── caatmaster.spec        # PyInstaller spec file
├── test_basic.py          # Basic tests
├── src/
│   ├── core/              # Core business logic
│   │   ├── database.py    # SQLAlchemy + SQLite setup
│   │   ├── models.py      # Database models
│   │   └── data_processor.py  # Polars data operations
│   ├── gui/               # GUI components
│   │   ├── main_window.py # Main application window
│   │   ├── views/         # Different views (Dashboard, Data, etc.)
│   │   ├── dialogs/       # Modal dialogs
│   │   ├── widgets/       # Custom widgets
│   │   └── themes/        # Styling
│   ├── services/          # Business services
│   └── utils/             # Utilities
├── resources/             # UI resources
│   └── stylesheets/       # Qt stylesheets
└── data/                  # Runtime data (created on first run)
```

## Installation

### Development Setup

1. **Clone or extract the repository**
   ```bash
   cd caatmaster_pyside
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the application**
   ```bash
   python main.py
   ```

### Building for Distribution

CAATmaster supports multiple build formats across platforms. Choose the one that fits your needs:

#### Quick Start (Universal)

```bash
# Auto-detects platform and builds appropriate format
python build.py
```

| Platform | Default Output | Alternative |
|----------|---------------|-------------|
| Windows | Portable directory | Single .exe |
| Linux | AppImage | Portable directory |
| macOS | Portable directory | N/A |

#### Windows Builds

**Option 1: Portable Directory** (Recommended - faster startup)
```bash
python build_windows.py
```
Output: `dist/CAATmaster/` folder (~300MB)

**Option 2: Single .exe** (Easier distribution, slower startup)
```python
# Edit build_windows.py, line 11:
BUILD_TYPE = "onefile"

# Then run:
python build_windows.py
```
Output: `dist/CAATmaster.exe` (~300MB)

#### Linux Builds

**Option 1: AppImage** (Recommended - single file, universal)
```bash
python build_appimage.py
```
Output: `CAATmaster-VERSION-x86_64.AppImage` (~400MB)

Run with:
```bash
chmod +x CAATmaster-*.AppImage
./CAATmaster-*.AppImage
```

**Option 2: Portable Directory**
```bash
python build_linux.py
```
Output: `dist/CAATmaster/` folder

#### Advanced Build Options

```bash
# Force specific build type
python build.py --type=portable    # Portable directory
python build.py --type=onefile     # Single .exe (Windows only)
python build.py --type=appimage    # AppImage (Linux only)

# Skip cleaning previous builds
python build.py --no-clean
```

#### Build Script Comparison

| Script | Platform | Output | Use Case |
|--------|----------|--------|----------|
| `build.py` | Auto | Smart default | Simple usage |
| `build_windows.py` | Windows | Folder or .exe | Windows deployment |
| `build_linux.py` | Linux | Folder | Simple Linux deploy |
| `build_appimage.py` | Linux | Single .AppImage | **Best for Linux** |

**Note:** You must build on each target platform. There's no cross-compilation for Python apps:
- Build on Windows → get Windows executable
- Build on Linux → get Linux executable
- Build on macOS → get macOS executable

## Usage

### First Run

On first run, the application will:
1. Create a `data/` directory
2. Initialize the SQLite database (`data/caatmaster.db`)
3. Open the main window

### Basic Workflow

1. **Create a Project**: File → New Project
2. **Import Data**: Click "Import Data" button or go to Data view
3. **Transform Data**: Apply transformations in the Transform view
4. **Visualize Data**: Create charts and graphs in the Visualizations view
5. **Run SQL Queries**: Use the Query view to write and execute SQL on your data
6. **Run Analysis**: Use ML/AI features in the Analyze view
7. **Manage Models**: Save, load, and manage trained ML models
8. **Generate Reports**: Create comprehensive reports with charts and tables
9. **Save Session**: Your work is automatically saved

### Supported File Formats

| Format | Extension | Notes |
|--------|-----------|-------|
| CSV | `.csv` | Configurable delimiter |
| Excel | `.xlsx`, `.xls` | All sheets supported |
| JSON | `.json` | Standard JSON format |
| Parquet | `.parquet` | High-performance format |

### SQL Query Editor

The Query view provides a full SQL editor for running SQL queries on your loaded data:

1. **Load Data**: Import data from the Data view first
2. **View Schema**: The schema browser shows all tables and columns
3. **Write Query**: Use the SQL editor with syntax highlighting
4. **Sample Queries**: Choose from pre-built query templates:
   - SELECT: Retrieve all data
   - FILTER: Apply WHERE clauses
   - AGGREGATE: Group by and aggregate
   - JOIN: Join multiple tables
   - ORDER: Sort results
   - CALCULATE: Create computed columns
5. **Validate**: Check query syntax before execution
6. **Execute**: Run the query and view results in the data table
7. **Export**: Export query results to CSV, Excel, Parquet, or JSON

**Requirements**: The SQL editor uses DuckDB internally. Ensure `duckdb` is installed:
```bash
pip install duckdb
```

### Data Visualizations

The Visualizations view provides interactive chart creation capabilities:

1. **Load Data**: Import data from the Data view first
2. **Select Chart Type**: Choose from 8 chart types:
   - **Bar Chart**: Compare categories (vertical or horizontal)
   - **Line Chart**: Show trends over time or categories
   - **Scatter Plot**: Explore relationships between variables
   - **Histogram**: View distribution of a single variable
   - **Pie Chart**: Show proportional distribution
   - **Box Plot**: Display statistical summaries and outliers
   - **Heatmap**: Visualize correlation matrices
   - **Area Chart**: Show cumulative trends
3. **Configure Options**: Select X/Y axes columns, grouping, colors
4. **Customize**: Set chart title, figure size, and other options
5. **Create Chart**: Click "Create Chart" to generate visualization
6. **Export**: Save charts to PNG, PDF, or SVG formats

**Chart Building Tips**:
- Use numeric columns for Y-axis values
- Use categorical columns for grouping and colors
- Histograms work with a single numeric column
- Heatmaps automatically show correlations between numeric columns
- Scatter plots can use color/size columns to show additional dimensions

### Report Generation

The Reports view provides comprehensive report generation capabilities:

**Quick Report** (One-click generation):
1. Load data from the Data view
2. Click "Generate Quick Report"
3. Choose save location
4. Report is auto-generated with:
   - Summary statistics (rows, columns, memory, nulls)
   - Column information table
   - Auto-generated chart (based on data types)
   - Sample data table

**Custom Report** (Build your own):
1. Click "Build Custom Report"
2. Add sections in desired order:
   - **Summary Statistics**: Overview cards and column details
   - **Text Section**: Add custom text content
   - **Chart Section**: Configure any of 8 chart types
   - **Data Table**: Show sample data with configurable row limit
3. Drag sections to reorder
4. Remove sections you don't need
5. Click "Generate Report"
6. Reports are saved as HTML files

**Report Features**:
- Professional styling with gradient cards
- Charts embedded as base64 images (no external files needed)
- Responsive design for different screen sizes
- Print to PDF directly from browser
- Recent reports tracking
- Double-click to open in default browser

**Tips**:
- Quick reports are perfect for rapid data exploration
- Custom reports are ideal for client deliverables
- Combine multiple charts and tables for comprehensive analysis
- Add text sections to explain findings and methodology

### User Authentication

CAATmaster includes a complete user authentication and management system:

**First Time Setup:**
1. On first launch, a default admin account is created automatically:
   - Username: `admin`
   - Password: `admin123`
   - **Important**: Change the default password after first login!

**Login:**
1. Login dialog appears on application startup
2. Enter username/email and password
3. Check "Remember me" to stay logged in between sessions
4. Click "Login" to authenticate

**Registration:**
1. Click "Register" on the login dialog
2. Fill in:
   - Username (unique, min 3 characters)
   - Email address
   - Full name (optional)
   - Password (min 6 characters)
   - Confirm password
3. Password strength indicator helps create secure passwords
4. After registration, you'll be automatically logged in

**User Management (Admin Only):**
1. Go to Settings → User Account tab
2. View all registered users in the table
3. Click "Add User" to create new accounts
4. Click "Delete" next to a user to remove them
5. Only administrators can manage other users

**Profile Management:**
1. Go to Settings → User Account tab
2. View your profile information:
   - Username
   - Email
   - Full Name
   - Role (User or Administrator)
   - Member Since date
   - Last Login timestamp
3. Click "Change Password" to update your password

**Security Features:**
- Passwords hashed with bcrypt (never stored in plain text)
- JWT tokens for secure session management
- Auto-login saves encrypted session locally
- Session expires after 24 hours
- Logout clears all session data

### ML Model Management

The ML Models view provides comprehensive model lifecycle management:

**Model Training and Saving:**
1. Train models in the Analyze view using ML operations
2. After training, models are automatically saved with metadata:
   - Model name and type
   - Target column used
   - Feature columns used
   - Performance metrics
   - Creation timestamp

**Model Inventory:**
1. Go to ML Models view
2. View all saved models in a table with:
   - Model name and type
   - Target column
   - Number of features
   - Performance metrics
   - Creation date
3. Filter models by type (Anomaly Detection, Classification, Clustering)
4. View statistics: total models, storage usage, models by type

**Model Operations:**
- **View Details**: Click "View" to see full model metadata
- **Load Model**: Load a model to use for predictions on new data
- **Export**: Export model to an external `.pkl` file
- **Delete**: Remove unwanted models (also deletes from disk)
- **Import**: Import models trained externally

**Supported Model Types:**
- **Anomaly Detection**: Isolation Forest, Local Outlier Factor, One-Class SVM
- **Classification**: Random Forest, Logistic Regression, KNN
- **Clustering**: K-Means, DBSCAN

**Using Saved Models:**
1. Load a model from the ML Models view
2. Navigate to Transform view with your data
3. Apply the model to generate predictions
4. Results appear as new columns in your data

**Best Practices:**
- Save models with descriptive names
- Document model purpose in description field
- Regularly clean up unused models to save disk space
- Export important models as backups

## Database Schema

The SQLite database includes the following tables:

- **users**: User accounts and authentication
- **projects**: Audit project metadata
- **datasets**: Imported dataset information
- **dataset_columns**: Column profiling data
- **ml_runs**: ML analysis runs and results
- **transformation_steps**: Applied transformation pipeline
- **project_sessions**: Saved analysis sessions
- **session_snapshots**: Session backup snapshots
- **ai_providers**: AI service configurations
- And more...

See `src/core/models.py` for the complete schema.

## Development

### Adding New Features

1. **New View**: Create in `src/gui/views/`, register in `main_window.py`
2. **New Service**: Add to `src/services/`
3. **New Transformation**: Add to `data_processor.py`
4. **Database Changes**: Update models and run migrations

### Styling

The application uses Qt Style Sheets (QSS). To modify the appearance:

1. Edit styles in individual widgets
2. Create a global stylesheet in `resources/stylesheets/`
3. Apply in `main.py` before creating widgets

### Testing

```bash
# Run tests
pytest

# Run with coverage
pytest --cov=src
```

## Distribution

### Windows Distribution

**Portable Directory** (Recommended)
```
CAATmaster/
├── CAATmaster.exe          # Main executable
├── start.bat               # Launcher script
├── start.ps1               # PowerShell launcher
├── README.txt              # User documentation
├── _internal/              # All dependencies
│   ├── Python DLLs
│   ├── PySide6/
│   ├── polars/
│   ├── sqlalchemy/
│   └── ... other packages
└── data/                   # Created at runtime
    └── caatmaster.db       # SQLite database
```

**Single .exe** (Alternative)
```
CAATmaster.exe              # Single file (~300MB)
README.txt
```
Data is stored in `%APPDATA%\CAATmaster\`

### Linux Distribution

**AppImage** (Recommended)
```
CAATmaster-VERSION-x86_64.AppImage    # Single file (~400MB)
```
Universal binary that works on all Linux distributions.

**Portable Directory** (Alternative)
```
CAATmaster/
├── CAATmaster            # ELF binary
├── start.sh              # Launcher script
├── README.txt
└── _internal/            # All dependencies
```

### Distribution Methods

1. **Direct Download**: Share the built archive (ZIP for Windows, .AppImage for Linux)
2. **Network Share**: Deploy portable directory to shared network drive
3. **USB Drive**: Copy portable directory to USB for portable use
4. **Package Managers** (Optional): Create .deb (Debian/Ubuntu) or .rpm (Fedora) packages

### Best Practices

| Use Case | Recommended Format | Reason |
|----------|-------------------|--------|
| Enterprise deployment | Portable directory | Faster startup, easier configuration |
| Public download | AppImage (Linux) / Single .exe (Windows) | Single file, simpler |
| Network/share | Portable directory | Better performance over network |
| USB distribution | Portable directory | Can run directly from USB |
| Quick testing | Single .exe / AppImage | No installation needed |

## Porting from procaat

This is a Qt-native port of the original procaat application. Key differences:

| Aspect | procaat (Web) | CAATmaster (Desktop) |
|--------|---------------|----------------------|
| Frontend | React + AG Grid | PySide 6 + QTableView |
| Backend | FastAPI + PostgreSQL | Embedded + SQLite |
| Deployment | Docker + web server | Portable directory |
| Data storage | Server-side | Local SQLite database |
| Authentication | JWT | Local user management |

### Known Limitations

- Multi-user collaboration requires database sharing
- No web-based access
- AI features require API keys from providers

## Roadmap

### Completed
- [x] Basic project structure
- [x] Database models (SQLite)
- [x] Main application window with navigation
- [x] Data import functionality (CSV, Excel, JSON, Parquet)
- [x] Basic data grid view with Polars integration
- [x] Multi-platform build scripts
  - [x] Portable directory (Windows/Linux/macOS)
  - [x] Single .exe (Windows)
  - [x] AppImage (Linux)
- [x] Data processor with transformation operations
- [x] Core views (Dashboard, Data, Transform, Analyze, etc.)
- [x] Transformation operations UI with 20+ operations:
  - Calculate: uppercase, lowercase, trim, capitalize, round, abs, log
  - Filter: equals, contains, range, null/not_null
  - Aggregate: sum, count, mean by group
  - Transform: rename, drop, cast, sort, select columns
- [x] Applied steps panel with undo functionality
- [x] Data export from Transform view
- [x] ML/AI/Audit operations as column generators:
  - ML: Anomaly detection, classification, risk scoring, model training
  - AI: Text classification, entity extraction, sentiment analysis, pattern learning
  - Audit: Benford's law, duplicate detection, gap analysis, outlier detection, round numbers
- [x] Project management UI
- [x] Session save/load functionality
- [x] Enhanced data export with HTML summary reports
- [x] All operations follow "everything generates a column" paradigm
- [x] SQL Query Editor:
  - Full SQL syntax support with syntax highlighting
  - Schema browser with table/column exploration
  - Query validation before execution
  - Sample queries for common operations
  - Export query results to multiple formats
  - Powered by DuckDB for SQL-on-Polars
- [x] Advanced Visualizations:
  - Bar charts (vertical/horizontal, grouped)
  - Line charts (single/multiple series)
  - Scatter plots (with color and size mapping)
  - Histograms (configurable bins)
  - Pie charts (categorical distribution)
  - Box plots (with/without grouping)
  - Heatmaps (correlation matrices)
  - Area charts (stacked)
  - Export charts to PNG, PDF, SVG
  - Interactive chart builder UI
- [x] Report Generation with Charts:
  - Quick report generation with auto-configured sections
  - Custom report builder with drag-and-drop sections
  - Summary statistics with data profiles
  - Embedded charts (all 8 chart types supported)
  - Data tables with configurable row limits
  - Text sections for custom content
  - HTML output with embedded base64 images
  - Professional styling with gradients and cards
  - Recent reports tracking
  - Open reports in default browser
- [x] User Authentication and Management:
  - Login and registration system
  - Secure password hashing with bcrypt
  - Session management with JWT tokens
  - Auto-login with saved sessions
  - User profile management in Settings
  - Change password functionality
  - Admin user management (create/delete users)
  - Default admin account (admin/admin123)
  - Logout functionality
- [x] Advanced ML Model Management:
  - Save trained models to disk and database
  - Load saved models for reuse
  - Model inventory with statistics
  - Export models to external files
  - Import models from external files
  - Model metadata (type, features, metrics)
  - Filter models by type
  - Delete unwanted models
  - Storage usage tracking
  - Model details viewer

### In Progress
(All planned features completed!)

## License

This project is based on procaat and maintains compatibility with its data formats and methodologies.

## Support

For issues, questions, or contributions, please refer to the original procaat documentation or open an issue in the repository.
