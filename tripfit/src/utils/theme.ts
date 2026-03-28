import { Platform } from 'react-native';

export const colors = {
  sand: '#F5F1E9',
  umber: '#5B4A3A',
  clay: '#C97B63',
  sky: '#6FA3B8',
  pine: '#2E4B3C',
  night: '#1A1A1A',
  cream: '#FFFDF8',
  fog: '#E6E1D8',
  coral: '#E0674B',
  gold: '#D3A44A',
};

export const font = {
  display: Platform.select({ ios: 'AvenirNext-DemiBold', android: 'sans-serif-medium', default: 'System' }),
  body: Platform.select({ ios: 'AvenirNext-Regular', android: 'sans-serif', default: 'System' }),
};

export const spacing = {
  xs: 6,
  sm: 10,
  md: 16,
  lg: 22,
  xl: 30,
};

export const radius = {
  sm: 10,
  md: 16,
  lg: 22,
};
