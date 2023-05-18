-- Direct SQLite to pretty-print output
.header on
.mode column

SELECT "ASSETS";

SELECT * FROM Asset;

SELECT "LICENSES";
SELECT * FROM License;

SELECT "FREQUENCY BANDS";
SELECT * FROM FrequencyBand;

SELECT "LICENSED FREQUENCY BANDS";
SELECT * FROM LicensedFrequency;

SELECT "CHANNELS";
SELECT * FROM Channel;

SELECT "CHANNEL FREQUENCIES";
SELECT * FROM ChannelFrequency;

SELECT "ASSET CHANNEL CONFIGS";
SELECT * FROM AssetChannelConfig;

SELECT "QUERYING FOR AVAILABLE FREQUENCIES AT ICEGS:";

SELECT A.id, F.id, F.low_mhz, F.high_mhz, F.space_to_earth, F.earth_to_space
  FROM Asset A 
  JOIN LicensedFrequency LF on LF.license_id = A.license_id
  JOIN FrequencyBand F on F.id = LF.band_id
  WHERE A.id = 'icegs';

CREATE VIEW AssetFrequencies (asset_id, band_id) AS
  SELECT A.id, F.id
    FROM Asset A 
    JOIN LicensedFrequency LF on LF.license_id = A.license_id
    JOIN FrequencyBand F on F.id = LF.band_id;

SELECT "QUERYING FOR REQUIRED FREQUENCIES BY CHANNELS:";

SELECT C.id, F.id
  FROM Channel C
  JOIN ChannelFrequency CF on CF.channel_id = C.id
  JOIN FrequencyBand F on F.id = CF.band_id;

CREATE VIEW ChannelFrequencies (channel_id, band_id) AS
  SELECT C.id, F.id
    FROM Channel C
    JOIN ChannelFrequency CF on CF.channel_id = C.id
    JOIN FrequencyBand F on F.id = CF.band_id;

SELECT "QUERYING FOR LEGAL CHANNELS BY ASSET (LIMIT 10)";

-- Here, query to get all of the combinations of (asset, frequency) and (channel, frequency) tuples
-- but filter them down to only those assets which have exactly the number of frequencies required
-- by each channel. Note that this relies on the fact that channels require all of their
-- frequencies. If we ever have an "OR" clause for the frequencies, we would need to re-do this
-- join -- and probably make it more complex. Fortunately, with the introduction of generic contact
-- types we can solve this by just creating separate channels for each side of the disjunction.
SELECT asset_id, channel_id
  FROM ChannelFrequencies CF 
  JOIN AssetFrequencies AF ON AF.band_id = CF.band_id 
  GROUP BY asset_id, channel_id 
  HAVING COUNT(channel_id) = (
    SELECT COUNT(*) AS needed_freqs 
    FROM ChannelFrequencies CFI 
    WHERE CFI.channel_id = CF.channel_id
  )
  LIMIT 10;

CREATE VIEW LegalChannels (asset_id, channel_id) AS
  SELECT asset_id, channel_id
    FROM ChannelFrequencies CF 
    JOIN AssetFrequencies AF ON AF.band_id = CF.band_id 
    GROUP BY asset_id, channel_id 
    HAVING COUNT(channel_id) = (
      SELECT COUNT(*) AS needed_freqs 
      FROM ChannelFrequencies CFI 
      WHERE CFI.channel_id = CF.channel_id
    );

SELECT "QUERYING FOR SHARED CHANNELS (LIMIT 10)";

SELECT A.asset_id, B.asset_id, A.channel_id 
  FROM LegalChannels A 
  JOIN LegalChannels B 
  ON A.asset_id <> B.asset_id 
  AND A.channel_id = B.channel_id
  LIMIT 10;

SELECT "QUERYING FOR ENABLED CHANNELS";

SELECT A.asset_id, B.asset_id, A.channel_id 
  FROM LegalChannels A 
  JOIN LegalChannels B 
  ON A.asset_id <> B.asset_id AND A.channel_id = B.channel_id 
  WHERE A.channel_id IN (
    SELECT channel_id 
    FROM AssetChannelConfig 
    WHERE asset_id = A.asset_id AND enabled = TRUE
  ) 
  AND B.channel_id IN (
    SELECT channel_id 
    FROM AssetChannelConfig 
    WHERE asset_id = B.asset_id AND enabled = TRUE
  )
  LIMIT 10;
