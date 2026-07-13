## ADDED Requirements

### Requirement: Windows-sensitive files SHALL use platform-appropriate protection

Portable encryption keys, pre-migration backups, and conversation archives SHALL use owner-only POSIX permissions on POSIX systems and a Windows access-control mechanism on Windows when the filesystem supports it.

#### Scenario: Sensitive file is created on Windows

- **WHEN** a key, database backup, or conversation archive is created
- **THEN** the application SHALL restrict access to the current user when supported
- **AND** failure to apply protection SHALL be reported without corrupting the file
