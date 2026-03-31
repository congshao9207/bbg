# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Trans-parser (流水处理平台) is a Flask-based transaction record parsing platform that processes bank transaction files (PDF, Excel, CSV) through OCR and data standardization pipelines. The system uses a multi-threaded worker architecture with Redis queuing and distributed locking.

## Development Setup

### Prerequisites
- Python 3.6
- Redis (for task queuing and distributed locks)
- MySQL (for data persistence)

### Installation
```bash
pip install -r base-image/requirements.txt
```

### Running the Application

**Local development:**
```bash
cd src
python app.py
```

**Production (uWSGI):**
```bash
cd src
uwsgi uwsgi.ini
```
The application runs on port 8011.

### Docker Build
```bash
./build.sh
docker build -t trans-parser ./src
```

## Testing

### Running Tests
```bash
# Install pytest
pip3 install pytest

# Run all tests
pytest

# Run specific test file
pytest tests/executors/executor_test.py

# Run specific test function
pytest tests/executors/executor_test.py::test_trans_01
```

### Test Structure
- `tests/executors/` - Parser executor tests
- `tests/component/` - Component unit tests
- `tests/app/` - Application and API tests

## Architecture

### Core Components

**Application Entry (`src/app.py`):**
- Flask REST API with endpoints for file upload, query, download, and deletion
- Initializes Eureka service registration, database connections, and worker threads
- Spawns `MAX_WORKERS` threads running `TransParseRouting` for background processing

**Worker Architecture (`src/component/trans_file_parse_routine.py`):**
- `TransParseRouting` threads continuously poll Redis queue for task IDs
- Routes tasks to appropriate scheduler based on file type:
  - `TaskScheduler` - for Excel/CSV files with existing OCR results
  - `TaskOcrScheduler` - for PDF files requiring OCR processing

**Task Processing Pipeline (`src/component/task_scheduler.py`):**
The system uses a chain-of-responsibility pattern with 10 sequential executors:

1. `TransFileLoadExecutor` - Load file into pandas DataFrame
2. `TransDataStandardization` - Normalize data formats
3. `RectifyExecutor` - Correct data errors
4. `TitleMatchExecutor` - Match column headers to standard schema
5. `TransTimeStandardization` - Standardize date/time formats
6. `TransAmountStandardization` - Normalize transaction amounts
7. `TransOpponentInfoStandardization` - Standardize counterparty information
8. `TransOtherInfoStandardization` - Standardize miscellaneous fields
9. `VerifyAuthenticityExecutor` - Verify data authenticity
10. `TransFlowRawData` - Persist to database

Each executor extends `TaskBaseExecutor` and implements the `execute()` method. Executors call `mark_err()` to signal failures, which stops the chain.

**Parse Context (`src/component/parse_context.py`):**
- Shared state object passed through the executor chain
- Contains `trans_data` (pandas DataFrame), column mappings, verification results
- Manages temporary file cleanup

**Distributed Locking:**
- Uses Redis distributed locks (`DistributedLockProxy`) keyed by `group_no`
- Prevents concurrent processing of related tasks
- Failed lock acquisition re-enqueues task with delay

### Key Directories

- `src/parser/impl/` - Transaction parsing executor implementations (trans_01 through trans_10)
- `src/component/` - Reusable components (file handling, OCR, scheduling)
- `src/ocr/` - OCR integration and result processing
- `src/detection/` - File type detection and splitting
- `src/model/` - SQLAlchemy ORM models
- `src/config/` - Configuration (database, file types, column mappings, response codes)
- `src/util/` - Utilities (Redis queue, file operations, serialization)
- `src/job/` - APScheduler background jobs

### API Endpoints

- `POST /trans/upload` - Upload transaction file for parsing
- `POST /trans/query` - Query parsing task status by `outReqNo`
- `POST /trans/excel/download` - Download parsed Excel result
- `GET /trans/rectify/download` - Download rectified transaction data
- `POST /trans/pre-parse` - Pre-parse file to extract metadata (row count, date range, bank info)
- `GET /trans/delete` - Delete transaction records (requires token)
- `POST /trans/ocr/result` - OCR callback endpoint
- `GET /health` - Health check
- `GET /info` - Database connection pool status

## Common Patterns

**Adding a New Executor:**
1. Create new file in `src/parser/impl/` following naming convention `trans_XX_description.py`
2. Extend `TaskBaseExecutor` from `src/parser/task_base_executor.py`
3. Implement `execute()` method, access `self.trans_data` for DataFrame
4. Call `self.mark_err(error_message)` on failure
5. Add to executor chain in `TaskScheduler._init_task_executor()`

**File Type Support:**
- Supported formats defined in `src/config/file_type.py` as `FileTypeEnum`
- PDF files trigger OCR workflow via `TaskOcrScheduler`
- Excel/CSV files processed directly via `TaskScheduler`

**Database Models:**
- `TransParseTask` - Main task tracking table
- `TransFlow` - Parsed transaction records
- `TransAttachment` - File attachments with binary data
- Models defined in `src/model/model.py`

## Configuration

Key configuration in `src/config/trans_config.py`:
- `MAX_WORKERS` - Number of worker threads
- `EUREKA_SERVER` - Service registry URL
- `WAITING_INTERVAL` - Queue polling interval
- `NAS_STORAGE_PATH` - File storage path

Database configuration in `src/config/db_config.py`.

## CI/CD

Jenkins pipelines defined in `Jenkinsfile*` files:
- Builds Docker image with tag format: `registry.cn-shanghai.aliyuncs.com/transformer/trans-parser:1.0.0-{branch}-{build_number}`
- Triggers deployment job after successful build



