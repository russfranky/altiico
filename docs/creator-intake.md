# Creator Intake — Design Notes

**Last updated:** 2026-04-23
**Status:** Not built. Parked pending completion of animation/manifest/PFP
work already in flight (see `docs/animation-pipeline.md`).

This document captures the design for a public-facing collection submission
flow — the stage *before* `avatar-api ingest` in the pipeline. Today,
ingestion is internal-only: a team member opens hubzz-admin and manually
triggers the pipeline for a collection. This doc describes the self-serve
version.

If you are picking this up cold, read top to bottom.

---

## 1. Problem

Today the onboarding flow for a new NFT collection is:

1. Creator messages a hubzz team member (Discord, email, DM)
2. Team member collects contract address, chain, sample VRMs, license info
   through back-and-forth
3. Team member opens hubzz-admin → Collections → triggers ingest manually
4. Creator has no visibility into status; hubzz has no paper trail; no
   license acceptance is recorded

Problems:

- **No scalable funnel.** Every submission is a DM thread.
- **Prep work falls on hubzz.** Team has to chase down missing info from
  creators who don't know what's needed.
- **No legal layer.** No record of the creator confirming they own the IP
  or authorize hubzz to host their VRMs.
- **No status visibility.** Creators ping repeatedly asking "is it live
  yet?" because there's nowhere to check.
- **No audit trail.** If a collection is later removed, there's no
  structured record of the original submission terms.

## 2. What we're borrowing from the industry

The pattern is standard: a structured intake form feeding a lifecycle state
machine, with submitter-visible status and explicit terms acceptance. Major
metaverse platforms that accept third-party IP all have some version of it.

**What hubzz copies:**
- Public-facing submission form
- Required-artifact checklist that forces prep work upfront
- Explicit status lifecycle visible to both sides
- One-time terms acceptance on submit

**What hubzz deliberately does NOT copy:**
- **Gated human approval as the only path.** Competitors use intake as a
  bottleneck to protect their brand. hubzz's advantage is being more open,
  not less. Approval exists as a quality gate but should not become a
  months-long queue.
- **In-house 3D production.** Competitors build avatars themselves from
  creator-supplied 2D art. hubzz accepts VRMs creators already have and
  passes them through optimize → R2. We are not an animation studio.
- **Single-IP lock-in.** Competitors lock themselves to one NFT family.
  hubzz is collection-agnostic; that is the moat.

## 3. Minimum viable intake (MVP — ~1 day)

### 3.1 Public form

Route: `/submit` or `/creators/apply` — decide based on IA but default to
`/submit` (shorter, matches pattern of other platforms).

Form fields (shadcn form, zod-validated):

- **Collection name** (string, required)
- **Contract address** (hex, required for on-chain; optional for off-chain
  drops)
- **Chain** (enum: Ethereum / Somnia / Solana / Base / Other; required)
- **Source pattern** (URL pattern with `{id}` placeholder, required — this
  is what avatar-api ingest needs. Example:
  `https://assets.example.com/avatars/{id}.vrm`)
- **Sample VRM URL** (direct .vrm link, required — used to preview before
  approval)
- **Token ID range** (from/to, required for on-chain collections)
- **License** (enum: CC0 / CC-BY / Proprietary / Other + free-text, required)
- **Creator wallet** (hex, required — used for future payouts or
  verification)
- **Contact email** (required — for status updates)
- **Description** (textarea, optional — short pitch)
- **Brand assets** (banner URL, pfp URL — optional, pre-fills
  `collections.banner_url` / `pfp_url`)
- **Terms acceptance** (checkbox, required) — one-time click-through:
  > "I confirm I own the IP rights to this collection (or am authorized
  > to submit it), I authorize hubzz to host optimized VRM copies of these
  > assets for use in-world, and I understand hosting may be revoked at
  > hubzz's discretion if the collection violates community standards or
  > IP terms."

### 3.2 Avatar-api endpoint

New table `collection_submissions` on `avatar-api/src/db.ts`:

```sql
CREATE TABLE collection_submissions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  collection_name TEXT NOT NULL,
  contract TEXT,
  chain TEXT NOT NULL,
  source_pattern TEXT NOT NULL,
  sample_vrm_url TEXT NOT NULL,
  token_range_from INTEGER,
  token_range_to INTEGER,
  license TEXT NOT NULL,
  license_notes TEXT,
  creator_wallet TEXT NOT NULL,
  contact_email TEXT NOT NULL,
  description TEXT,
  banner_url TEXT,
  pfp_url TEXT,
  terms_accepted_at TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending',  -- see §3.4
  admin_notes TEXT,                         -- internal-only
  submitted_at TEXT NOT NULL,
  reviewed_at TEXT,
  reviewed_by TEXT,                         -- admin wallet or hbz_ token id
  approved_collection_slug TEXT             -- FK to collections.slug on approval
);
```

New endpoints:

- `POST /submissions` — public, rate-limited (1 submission per email per
  24h). Accepts form payload, validates, writes row with `status='pending'`,
  returns submission ID + tracking URL.
- `GET /submissions/:id/status` — public, returns current status and any
  public-facing admin notes. Used by creator to check progress.
- `GET /admin/submissions` — admin-only (`hbz_` token + admin permission).
  Returns all submissions with optional status filter.
- `PATCH /admin/submissions/:id` — admin-only. Updates status, admin_notes,
  and on approval creates the `collections` row and kicks off ingest.

### 3.3 Admin tab

New tab in hubzz-admin: `/admin/submissions` (or extend the existing
Collections tab with a "Submissions" subtab).

For each submission row:
- Summary: collection name, chain, status badge, submitted time
- Detail view: all form fields, terms acceptance timestamp, sample VRM
  preview (load via ualLoader-style VRM viewer, reuse altiico's
  `AnimationPreviewPage` component if possible)
- Action buttons: **Approve & ingest** / **Request changes** /
  **Reject** / **Add internal note**

Approve flow:
1. Admin reviews sample VRM + license + brand assets
2. Clicks **Approve & ingest**
3. Backend creates a `collections` row from the submission (slug generated
   from collection_name), kicks off existing ingest job, flips submission
   status to `ingesting`, stores `approved_collection_slug` FK
4. Submission page for the creator now shows "Ingesting X of Y avatars"

Request-changes flow:
1. Admin flips status to `changes_requested`
2. Admin writes a public-facing message in `admin_notes`
3. Creator sees the message on status page, resubmits with edits

### 3.4 Status lifecycle

```
pending            → submitted, awaiting review
under_review       → admin actively looking at it
changes_requested  → admin needs the creator to fix something
approved           → admin approved, ingest not yet started
ingesting          → avatar-api ingest job running
live               → collection is published, avatars available in-world
rejected           → not approved (with reason in admin_notes)
withdrawn          → creator withdrew the submission
```

Transitions (admin-only except `withdrawn`):

```
pending → under_review → approved → ingesting → live
                     ↘ changes_requested → pending (after resubmit)
                     ↘ rejected
any → withdrawn (creator action)
```

### 3.5 Notification loop

MVP: **console.log only**. Wire real email later when volume justifies it.

Event triggers (fire `console.log` + write to a `submission_events` audit
table):
- On submit: "new submission received"
- On status change: "status changed from X to Y"
- On admin note: "admin added note"

Future: swap console.log for Postmark or Resend when submissions exceed
~10/week. Creator gets email on every status change. Template per status.

## 4. Why we are NOT building this today

User priorities in flight:

1. Finish the JSON manifest + FB thumbnail R2 upload path (avatar-api
   endpoints)
2. Audit + prune unused Mixamo FBX files
3. Decide whether to port UAL loader into hubzz client

These are existing commitments. Creator intake is a net-new feature. Until
at least #1 lands, intake is parked.

**When to start:** after the animation pipeline work is at a stopping
point AND there is evidence of creator-intake friction (multiple DM threads
in a week, creators dropping off due to opaque process, or a legal concern
about hosting VRMs without recorded terms).

## 5. Where it fits in the existing pipeline

Today's Pipeline page (`altiico/src/pages/PipelinePage.tsx`) has this flow:

```
Source → avatar-api ingest → vrm-optimizer → R2 → hubzz-admin → altiico QA → hubzz engine → In-world
```

Creator intake slots in before `avatar-api ingest`:

```
Creator submission → [admin review gate] → avatar-api ingest → …
```

When this ships, add a new node at the front of the `NODES` array in
`PipelinePage.tsx` with:

- `id: 'intake'`
- `title: 'Creator intake'`
- `owner: 'hubzz-admin'`
- `liveStatus: 'submissions'` (new live counter)
- Live text: `N pending / M under review / K approved this week`

## 6. Open questions

- [ ] **Auth for submission.** Require Privy wallet login, or allow
      anonymous submit with just email? Wallet login is safer (links
      submission to a verified identity) but adds a step. Default: require
      wallet login.
- [ ] **Chain coverage at launch.** Start with Ethereum only, or include
      Somnia/Base/Solana from day one? Default: Ethereum + Somnia (what
      hubzz already supports); defer others.
- [ ] **Who reviews submissions.** Every admin with the permission, or a
      dedicated reviewer role? Default: any admin; refine later.
- [ ] **Auto-approve CC0 open-source collections?** If license=CC0 and
      source is an allowlisted domain (e.g. Quaternius, OpenSourceAvatars),
      skip human review and go straight to ingest. Nice-to-have, not MVP.
- [ ] **Creator rev-share placeholder.** `creator_wallet` field is captured
      for future payouts (sponsored gas, stub revenue share). No current
      payout system exists. Just capture the data now.
- [ ] **Withdrawal vs. takedown.** `withdrawn` = creator-initiated.
      Separate `takedown` status for hubzz-initiated removal after
      community-standards violation? Default: yes, add `takedown` as a
      terminal status with mandatory `admin_notes`.
- [ ] **Licensing refresh.** If a creator submits and later changes their
      license terms (e.g. CC0 → Proprietary), is there a flow to re-accept?
      Default: force a new submission on material terms change.

## 7. Licensing layer

**This is the real legal win of the intake flow.** Today hubzz hosts VRMs
with no recorded creator consent. The terms-acceptance checkbox + stored
`terms_accepted_at` timestamp create the paper trail.

Specific terms that must be in the click-through (consult legal before
going live):

1. Creator confirms IP ownership or authorization.
2. Creator grants hubzz a non-exclusive, revocable, worldwide license to
   host optimized VRM copies for in-world use.
3. Creator acknowledges hubzz may remove the collection at any time for
   community-standards violations.
4. Creator acknowledges assets may be cached on CDN (Cloudflare R2) and
   complete removal from caches may take up to 24h.
5. Creator acknowledges no payout is guaranteed today; any future
   revenue-share terms will be negotiated separately.

Store the exact terms text as a `terms_version` column so old submissions
reference the terms they actually agreed to, not whatever the current text
says.

## 8. Anti-goals

Things this intake flow explicitly does NOT do:

- **Replace hubzz-admin's direct collection management.** Admins can still
  add a collection manually (e.g. for first-party drops). Intake is one
  path, not the only path.
- **Become a marketplace.** No listing fees, no featured slots, no
  bidding. Intake is about getting 3D avatars into hubzz, not monetizing
  the onboarding.
- **Gate altiico QA.** altiico's QA workflow stays open to hubzz team
  regardless of submission source. altiico is internal tooling; intake is
  a public funnel.
- **Replace DM/Discord conversations.** The form captures the artifacts.
  Back-and-forth about creative direction, timing, launch coordination
  still happens in Discord. Intake is the paper trail, not the whole
  relationship.
