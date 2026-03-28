# TravelHabit MVP

React Native (Expo) MVP for a travel-fitness app with PaceMeet.

## Paywall Logic (Profile-based)

Inputs
- Trip length: `1-7`, `8-14`, `15+`
- Trip type: `business`, `leisure`, `frequent`
- Time per day: `10-15`, `20-30`, `30+`
- Equipment: `none`, `bands`, `hotel-gym`
- Training time: `morning`, `midday`, `evening`

Onboarding flow
- Multi-step personalization with a goal-summary step.
- Paywall presented at the end of onboarding (primary + secondary offer).

Decision rules
- If `1-7` days: show `Trip Pass` as primary
- If `8-14` days: show `7-day trial` as primary
- If `15+` days or `frequent`: show `7-day trial` + annual anchor
- Secondary offer: alternate between `Trip Pass` and `3-day trial`

## Analytics Events (MVP)

Core funnel
- `onboarding_complete` { tripLength, tripType, goal }
- `paywall_view` { primaryOffer, secondaryOffer }
- `offer_primary_click` { offer }
- `offer_secondary_click` { offer }
- `purchase_success` { offer }
- `trial_start` { offer }
- `trial_convert` { offer }
- `refund` { offer }

Engagement
- `workout_open` { workoutId }
- `workout_complete` { workoutId }
- `open_pacemeet_from_home`
- `meetup_create_tap`
- `meetup_join` { id }
- `location_request`

## Run

```bash
cd tripfit
npm install
npm run start
```

Note: IAP and location are mocked in the UI right now.
