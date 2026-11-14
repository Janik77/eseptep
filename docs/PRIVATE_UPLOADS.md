# Private uploads: operator checklist (not deployed)

New uploads use PRIVATE_MEDIA_ROOT, never a public media URL. Reads and estimates
are scoped to authenticated owner or original guest session; missing legacy guest
ownership fails closed. Logging in does not silently claim guest or legacy uploads.
The download endpoint forces attachment/octet-stream, no-store and nosniff.

Validation: 10 MB, JPEG/PNG/WEBP decoded and re-encoded (20 MP ceiling), PDF parsed
strictly (1–100 pages, no encryption or detected active/embedded content). MIME
reported by browser is not trusted. DWG is explicitly unsupported until a sandboxed
CAD validator exists. PDF validation is NOT malware scanning; attachments remain
untrusted. Use antivirus/content-disarm and isolated processing before real-client
production intake. Application upload limits do not replace proxy request limits.

## Existing VPS media requires operator action BEFORE public rollout

1. Back up database and media; inventory actual nginx/CDN aliases. We did not access
   or modify the VPS. Freeze uploads during copying and switch-over.
2. Disable public access to legacy directories at nginx/CDN and invalidate caches:
   ```nginx
   # Place before broader regex media handlers; ^~ prevents regex bypass.
   location ^~ /media/project_uploads/ { return 404; }
   location ^~ /media/projects/ { return 404; }
   client_max_body_size 12m;
   ```
   Apply equivalent protection to EVERY historical alias and direct object URL.
   Never alias PRIVATE_MEDIA_ROOT; it must be outside public server roots.
3. Run migrations and `python manage.py copy_legacy_private_uploads` (dry run), then
   `python manage.py copy_legacy_private_uploads --apply` after reviewing output.
   Copies preserve DB names; originals are NOT deleted. Resolve conflicts manually.
4. Confirm owner download succeeds and anonymous/other-user/old media URL requests
   fail using both application and actual public origin. Test CDN cache bypass.
5. Only after verified backups and access checks, operator quarantines/removes public
   originals under a separately approved retention process. Do not bulk-assign
   guest files to users. Historical files were not validated: quarantine/revalidate
   before use. RenovationProject files have no ownership model and remain blocked,
   not exposed by the new download route.

The Django development route serves only public avatars/masters namespaces,
rejects traversal/encoded leftovers and resolves paths before containment checks.
No generic development media helper remains. PDF validation also rejects file
attachment annotations, associated files and embedded file specifications. This does not protect a VPS nginx alias by itself.
