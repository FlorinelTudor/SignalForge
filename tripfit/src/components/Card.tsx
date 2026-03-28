import React from 'react';
import { StyleSheet, View } from 'react-native';
import { colors, radius, spacing } from '../utils/theme';

type Props = {
  children: React.ReactNode;
  tone?: 'light' | 'dark' | 'accent';
};

export function Card({ children, tone = 'light' }: Props) {
  return (
    <View style={[styles.card, toneStyles[tone]]}>
      {children}
    </View>
  );
}

const toneStyles = StyleSheet.create({
  light: {
    backgroundColor: colors.cream,
  },
  dark: {
    backgroundColor: colors.umber,
  },
  accent: {
    backgroundColor: colors.clay,
  },
});

const styles = StyleSheet.create({
  card: {
    padding: spacing.md,
    borderRadius: radius.lg,
    shadowColor: '#000',
    shadowOpacity: 0.08,
    shadowRadius: 10,
    shadowOffset: { width: 0, height: 6 },
    elevation: 2,
  },
});
