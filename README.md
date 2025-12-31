# Satellite Imagery Monitor

Automated monitoring of satellite imagery updates for location: **35°09'55.3"N 106°44'46.4"W** (New Mexico, USA)

## How It Works

- Runs weekly (every Monday at 00:00 UTC)
- Downloads satellite tile from Esri World Imagery (free, no API key)
- Compares with previous imagery using perceptual hashing
- Only saves and commits when imagery actually changes
- Sends email notification on updates

## Setup

1. Fork this repository
2. Add GitHub Secrets (Settings → Secrets and variables → Actions):
   - `LATITUDE`: `35.165361`
   - `LONGITUDE`: `-106.746222`
   - `EMAIL_USERNAME`: Your Gmail address
   - `EMAIL_PASSWORD`: Gmail app password
   - `NOTIFICATION_EMAIL`: Where to receive alerts

3. Enable GitHub Actions in your repository
4. Manual trigger: Actions → Monitor Satellite Imagery → Run workflow

## Imagery History

All detected imagery changes are saved with timestamps in the repository.