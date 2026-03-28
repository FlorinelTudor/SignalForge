import React, { useEffect } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { Card } from '../components/Card';
import { PrimaryButton } from '../components/PrimaryButton';
import { track } from '../utils/analytics';
import { offerMatrix, Profile } from '../utils/pricing';
import { colors, font, spacing } from '../utils/theme';

type Props = {
  profile: Profile;
  onReset: () => void;
};

export function ProfileScreen({ profile, onReset }: Props) {
  const { primary, secondary } = offerMatrix(profile);

  useEffect(() => {
    track('paywall_view', { primaryOffer: primary.kind, secondaryOffer: secondary.kind });
  }, [primary.kind, secondary.kind]);

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Profile</Text>
      <Card>
        <Text style={styles.label}>Trip length</Text>
        <Text style={styles.value}>{profile.tripLength} days</Text>
        <Text style={styles.label}>Trip type</Text>
        <Text style={styles.value}>{profile.tripType}</Text>
        <Text style={styles.label}>Focus</Text>
        <Text style={styles.value}>{profile.goal}</Text>
        <View style={styles.spacer} />
        <PrimaryButton label="Edit trip profile" onPress={onReset} />
      </Card>

      <Card tone="accent">
        <Text style={styles.offerTitle}>{primary.title}</Text>
        <Text style={styles.offerText}>{primary.price}</Text>
        <Text style={styles.offerText}>{primary.detail}</Text>
        <View style={styles.spacer} />
        <PrimaryButton
          label={primary.cta}
          onPress={() => track('offer_primary_click', { offer: primary.kind })}
        />
        <View style={styles.divider} />
        <Pressable onPress={() => track('offer_secondary_click', { offer: secondary.kind })}>
          <Text style={styles.offerText}>Backup option: {secondary.title}</Text>
        </Pressable>
      </Card>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    padding: spacing.lg,
    gap: spacing.md,
  },
  title: {
    fontFamily: font.display,
    fontSize: 24,
    color: colors.night,
  },
  label: {
    fontFamily: font.body,
    color: colors.umber,
    marginTop: spacing.sm,
  },
  value: {
    fontFamily: font.display,
    fontSize: 16,
    color: colors.night,
  },
  offerTitle: {
    fontFamily: font.display,
    fontSize: 18,
    color: colors.cream,
  },
  offerText: {
    fontFamily: font.body,
    color: colors.cream,
    marginTop: spacing.xs,
  },
  spacer: {
    height: spacing.sm,
  },
  divider: {
    height: 1,
    backgroundColor: 'rgba(255,255,255,0.3)',
    marginVertical: spacing.sm,
  },
});
