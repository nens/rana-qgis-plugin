# Download Worker Class Diagram

## Overview

The download worker system separates the concerns of **where** files are saved, **what** needs to be downloaded, and **how** the download is coordinated. 

**Download contexts** determine the destination path and styling retrieval strategy. For example, tenant files go into project-based folders, while schematisations go into temporary directories.

**Downloaders** know what to download and how to process it. They receive a context at construction time, fetch files from the appropriate API (Rana or 3Di), and perform any necessary post-processing like extracting archives or upgrading schemas.

**Workers** coordinate the download in background threads to keep the UI responsive. They create downloaders, run them, and communicate progress and results back to the main thread via Qt signals.

This separation means you can mix and match contexts with downloaders (e.g., download a schematisation to either a temp directory or a project folder) without duplicating code, and new download types can be added by creating new context or downloader classes. 

```mermaid
classDiagram
    %% Abstract Base Classes
    class AbstractDownloadContext {
        <<abstract>>
        +local_dir: Path
        +local_file_path: Path
        +get_style_zip()*
    }

    class BaseDownloader {
        <<abstract>>
        -download_context: AbstractDownloadContext
        +url: str*
        +downloaded_file_path: Path
        +download_file(signals, download_file=True)
        +postprocess()*
        +_handle_qml_extraction(local_dir_structure)*
    }

    %% Download Context Implementations
    class TempDownloadContext {
        -file_name: str
        +local_dir: Path
        +local_file_path: Path
        +get_style_zip()
    }

    class FileDownloadContext {
        -project_slug: str
        -file_id: str
        -file_descriptor_id: str
        -file_data_type: str
        +local_dir: Path
        +local_file_path: Path
        +get_style_zip()
    }

    class PublicationFileDownloadContext {
        -project_slug: str
        -publication_version: dict
        -file_data: RanaPublicationFileData
        +local_dir: Path
        +local_file_path: Path
        +get_style_zip() Optional[bytes]
    }

    %% Downloader Implementations
    class RanaDownloader {
        -project: dict
        -file: dict
        +postprocess()
        +_handle_qml_extraction(local_dir_structure)
    }

    class SchematisationDownloader {
        -schematisation_id: int
        -revision: dict
        -_downloaded_file_path: Path
        -progress_signal: Optional[pyqtSignal]
        -warning_signal: Optional[pyqtSignal]
        +url: str
        +downloaded_file_path: Path
        +download_file(signals, download_file=True)
        +postprocess()
        -_upgrade_schematisation(schematisation_filepath) Optional[Path]
        +_handle_qml_extraction(local_dir_structure)
    }

    class RanaFileDownloader {
        +url: Optional[str]
    }

    %% Worker Classes
    class SingleFileDownloadWorker {
        <<QThread>>
        +signals: FileDownloadWorkerSignals
        -downloader: BaseDownloader
        +run()
    }

    class BatchFileDownloadWorker {
        <<QThread>>
        +signals: FileDownloadWorkerSignals
        -downloaders: list[BaseDownloader]
        -downloaded_files: dict
        +unique_file_ids: set[str]
        +nof_files: int
        +handle_existing(downloader) bool
        +run()
    }

    %% Relationships
    AbstractDownloadContext <|-- TempDownloadContext
    AbstractDownloadContext <|-- FileDownloadContext
    AbstractDownloadContext <|-- PublicationFileDownloadContext

    BaseDownloader <|-- RanaDownloader
    BaseDownloader <|-- SchematisationDownloader
    RanaDownloader <|-- RanaFileDownloader

    BaseDownloader *-- AbstractDownloadContext : contains

    SingleFileDownloadWorker o-- BaseDownloader : uses
    BatchFileDownloadWorker o-- BaseDownloader : uses multiple
```


## Download Contexts

Download contexts implement the **where** and **styling** aspects of downloading:

- **TempDownloadContext**: Creates temporary directories under `rana_downloads/` for transient files (e.g., schematisations during processing)
  - Used for files that don't need persistent project-based storage
  - Automatically creates unique temporary subdirectories

- **FileDownloadContext**: Manages downloads for tenant files within a project structure
  - Uses `get_local_dir_structure()` to create project/file-based paths
  - Retrieves QML styling from file descriptors via API
  - Typical use: downloading individual project files from Rana

- **PublicationFileDownloadContext**: Handles publication-specific versioned downloads
  - Creates directory structure based on publication version and file tree
  - Retrieves QML styling from publications (with fallback to file descriptor)
  - Preserves publication folder hierarchy during download

All contexts provide:
- `local_dir`: The directory where the file will be saved
- `local_file_path`: The complete path including filename
- `get_style_zip()`: Retrieves QML styling data (if applicable)

## Downloaders

Downloaders implement the **what** and **how** aspects of downloading:

- **RanaDownloader**: Base class for Rana tenant files
  - Downloads files from Rana tenant API
  - Extracts QML styling for vector/raster files during post-processing
  - Abstract `url` property must be provided by subclasses

- **RanaFileDownloader**: Concrete Rana downloader
  - Generates download URLs using `get_tenant_file_url()`
  - Inherits QML extraction from `RanaDownloader`

- **SchematisationDownloader**: Specialized downloader for 3Di schematisations
  - Downloads from 3Di API using schematisation and revision IDs
  - Post-processes by:
    1. Extracting the zip archive
    2. Upgrading schematisation to latest schema version (with error handling)
    3. Adding revision number to filename (e.g., `model (rev5).gpkg`)
  - Uses cached URL property to avoid repeated API calls
  - Emits warnings if upgrade fails (continues with original version)

All downloaders provide:
- `download_file()`: Core download logic with progress tracking and error handling
- `postprocess()`: File processing after download (extraction, transformation)
- `_handle_qml_extraction()`: QML styling extraction for supported file types

## Workers

Workers coordinate the download process in separate QThreads to prevent UI blocking:

- **SingleFileDownloadWorker**: Simple worker for downloading one file
  - Creates a `FileDownloadWorkerSignals` instance for communication
  - Calls `downloader.download_file()` in the thread's `run()` method
  - Used for on-demand single file downloads

- **BatchFileDownloadWorker**: Optimized worker for downloading multiple files
  - Downloads unique files only once (deduplication by file ID)
  - Copies already-downloaded files to additional required locations
  - Tracks downloaded file paths in `downloaded_files` dictionary
  - Useful when multiple layers reference the same underlying file
  - Emits `all_finished` signal after entire batch completes

Both workers:
- Inherit from `QThread` for background execution
- Use `FileDownloadWorkerSignals` for Qt signal-based communication
- Emit progress updates (percentage + current file)
- Emit success (`finished`) or failure (`failed`) signals
- Support warning messages (e.g., schema upgrade failures)

## Signal Communication
All workers use **FileDownloadWorkerSignals** to communicate with the main thread:
- `progress(int, str)`: Download progress percentage and current file message
- `finished()`: Individual file download completed successfully
- `failed(str)`: Download failed with error message
- `all_finished()`: All files in batch completed (BatchFileDownloadWorker only)
- `warning(str)`: Non-fatal warnings (e.g., schematisation upgrade issues)


## Usage in Loader

The Loader class demonstrates three main usage patterns for the download workers:

### 1. Single File Download (Tenant Files)

- Uses `FileDownloadContext` to save to project-specific directories in `files` folder and downloads styling for file from Rana
- Uses `RanaFileDownloader` to fetch from tenant API
- `SingleFileDownloadWorker` handles everything for a single file


### 2. Batch Download (Publications)

- Uses `PublicationFileDownloadContext` to save to publication specific directories in `publications` folder of the project and downloads layer specific styling from Rana
- Creates multiple `RanaFileDownloader` instances, one per file
- `BatchFileDownloadWorker` handles downloading multiple files:
  - automatically deduplicates files by ID
  - asks confirmation for large downloads (>10 files)


### 3. Schematisation export

**Key points:**
- Uses `TempDownloadContext` for transient files
- `SchematisationDownloader` fetches from 3Di API and automatically extracts zip, upgrades schema, adds revision number to filename
- `SingleFileDownloadWorker` handles everything for a single file


