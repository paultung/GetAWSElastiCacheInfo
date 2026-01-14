# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Cross-region automatic query for Global Datastore members
- Progress indicator for multi-region queries
- Role field display (Primary/Secondary) for Global Datastore members
- Automatic region discovery from Global Datastore topology
- Results sorted by region alphabetically

### Fixed
- **Critical**: Fixed empty Role field for Global Datastore members by adding `ShowMemberInfo=True` parameter to `describe_global_replication_groups` API call
  - Without this parameter, AWS API returns empty Members array by default
  - This prevented the tool from identifying Global Datastore members across regions
  - Impact: Role field now correctly displays "Primary" or "Secondary"
  - Impact: Secondary clusters in other regions are now automatically discovered and queried

### Changed
- Refactored `_get_global_datastores()` to parse Members array with complete region information
- Modified `_convert_to_model()` to accept `current_region` parameter for accurate region assignment
- Enhanced error handling with graceful degradation for region query failures

### Technical Details
- Added `_query_single_region()` helper method to encapsulate single-region query logic
- Implemented sequential multi-region query with independent ElastiCache clients per region
- Updated `global_ds_map` structure from 2-layer to 3-layer: `{region: {rg_id: {global_ds_id, role}}}`
- Role values stored as uppercase ("PRIMARY"/"SECONDARY") and displayed with capitalization ("Primary"/"Secondary")

## [0.1.0] - 2026-01-14

### Initial Release
- Query ElastiCache clusters across Redis OSS, Valkey, and Memcached engines
- 18 configurable information fields
- CSV and Markdown output formats
- Cluster name filtering with wildcard support
- Rich terminal display with progress indicators
- AWS profile support
- Comprehensive error handling with Chinese error messages
