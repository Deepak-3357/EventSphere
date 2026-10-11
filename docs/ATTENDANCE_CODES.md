# Attendance codes

Phase 2 adds one six-digit code per active registration. Because the existing
attendance table records attendance per registration, a team registration has
one shared code; individual registrations have one code each.

Codes are generated with Python's `secrets` module. The database stores an
event-scoped HMAC digest for lookup and encrypted ciphertext for the owning
student's event pass. Plaintext codes are never logged or stored. Codes are
revoked when a registration is cancelled and a new code is issued when that
registration is reactivated.

Both QR and manual check-in call the same `_record_attendance` transaction.
Manual lookup is scoped by event, requires an active registration, and does
not accept a client-supplied student or registration ID.

## Migration and backfill

Apply `20261011100000_attendance_codes.sql` after the existing registration and
attendance migrations. The migration is additive and does not alter existing
attendance records. Existing active registrations receive a code lazily on
their next authorized event-pass/code request. New registrations receive a
code in the registration transaction. A production backfill may call the
same service in a controlled batch; do not generate codes in a public SQL
query or expose them in a bulk response.

Rollback is application-first: disable the manual-code UI and endpoint while
leaving the additive tables in place. Dropping the tables is not a safe
rollback because issued-code history and registration references may exist.

## Required backend settings

Configure these in Render's backend environment, never in source control:

```text
ATTENDANCE_CODE_SECRET=<long random server secret>
ATTENDANCE_CODE_ENCRYPTION_KEY=<Fernet key generated for this deployment>
ATTENDANCE_CODE_MAX_FAILURES=5
ATTENDANCE_CODE_RATE_WINDOW_SECONDS=60
ATTENDANCE_CODE_LOCK_SECONDS=60
```

The implementation has a compatibility fallback that derives the encryption
key from the existing attendance signing secret when the dedicated settings
are absent. Production should still set both dedicated values and preserve
them across deploys; changing either secret invalidates existing codes or
prevents them from being decrypted.
