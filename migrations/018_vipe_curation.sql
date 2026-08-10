-- 018_vipe_curation.sql
--
-- Import the VIPE platform's own curation from the altii.co mirror
-- (data/altii_vipe_mirror.json). VIPE listed these collections with a taxonomy
-- and setup notes that this catalog had no equivalent for.
--
--   vipe_category      VIPE's taxonomy (Genesis Collections, Classic Meta,
--                      Metaverse Ready, Avatar Standard, Fashion Meta,
--                      Voxel Meta, The Great Archive, Curated Collections)
--   vipe_assets_3d     how the collection ships 3D ("3D Ready", "GLB",
--                      "Voxel · T-Pose", "3D Ready · FBX · VXR", …)
--   vipe_metadata_param  which metadata field holds the VRM ('asset' | 'vrm')
--   curated_description  the hand-written description from the mirror; better
--                      than the OpenSea blurb, so the UI prefers it
--   vipe_listed        1 = VIPE listed this collection
--
-- Apply:  sqlite3 data/vrm_index.db < migrations/018_vipe_curation.sql

ALTER TABLE collections ADD COLUMN vipe_category       TEXT;
ALTER TABLE collections ADD COLUMN vipe_assets_3d      TEXT;
ALTER TABLE collections ADD COLUMN vipe_metadata_param TEXT;
ALTER TABLE collections ADD COLUMN curated_description TEXT;
ALTER TABLE collections ADD COLUMN vipe_listed         INTEGER;
