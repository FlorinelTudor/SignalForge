import { Offer, OfferKind, offers } from '../data/offers';

export type TripLength = '1-7' | '8-14' | '15+';
export type TripType = 'business' | 'leisure' | 'frequent';

export type Profile = {
  tripLength: TripLength;
  tripType: TripType;
  goal: 'run' | 'lift' | 'both';
};

export function recommendOffer(profile: Profile): Offer {
  const { tripLength, tripType } = profile;

  if (tripLength === '1-7') {
    return offers['trip-pass'];
  }

  if (tripType === 'frequent') {
    return offers['trial-7'];
  }

  if (tripLength === '8-14') {
    return offers['trial-7'];
  }

  return offers['trial-7'];
}

export function fallbackOffer(profile: Profile): Offer {
  if (profile.tripLength === '1-7') {
    return offers['trial-3'];
  }
  return offers['trip-pass'];
}

export function offerMatrix(profile: Profile): { primary: Offer; secondary: Offer } {
  const primary = recommendOffer(profile);
  const secondaryKind: OfferKind = primary.kind === 'trip-pass' ? 'trial-3' : 'trip-pass';
  return { primary, secondary: offers[secondaryKind] };
}
