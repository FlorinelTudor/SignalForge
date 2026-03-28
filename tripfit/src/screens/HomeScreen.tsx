import React, { useEffect } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { Card } from '../components/Card';
import { PrimaryButton } from '../components/PrimaryButton';
import { Tag } from '../components/Tag';
import { offers } from '../data/offers';
import { workouts } from '../data/workouts';
import { track } from '../utils/analytics';
import { offerMatrix, Profile } from '../utils/pricing';
import { colors, font, spacing } from '../utils/theme';

type Props = {
  profile: Profile;
};

export function HomeScreen({ profile }: Props) {
  const { primary, secondary } = offerMatrix(profile);
  const workout = workouts[0];

  useEffect(() => {
    track('paywall_view', { primaryOffer: primary.kind, secondaryOffer: secondary.kind });
  }, [primary.kind, secondary.kind]);

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Trip Plan</Text>
      <Card>
        <Text style={styles.cardTitle}>Today</Text>
        <Text style={styles.cardHeadline}>{workout.title}</Text>
        <View style={styles.row}>
          <Tag label={`${workout.durationMin} min`} />
          <Tag label={workout.focus.toUpperCase()} />
          <Tag label={workout.intensity} />
        </View>
        <Text style={styles.cardBody}>{workout.steps[0]}</Text>
      </Card>

      <Card tone="accent">
        <Text style={styles.cardTitleDark}>Recommended Offer</Text>
        <Text style={styles.cardHeadlineDark}>{primary.title}</Text>
        <Text style={styles.cardBodyDark}>{primary.price}</Text>
        <Text style={styles.cardBodyDark}>{primary.detail}</Text>
        <View style={styles.spacer} />
        <PrimaryButton
          label={primary.cta}
          onPress={() => track('offer_primary_click', { offer: primary.kind })}
        />
        <View style={styles.divider} />
        <Text style={styles.cardBodyDark}>Prefer another option?</Text>
        <Pressable
          onPress={() => track('offer_secondary_click', { offer: secondary.kind })}
        >
          <Text style={styles.secondaryText}>{offers[secondary.kind].title}</Text>
        </Pressable>
      </Card>

      <Card>
        <Text style={styles.cardTitle}>PaceMeet today</Text>
        <Text style={styles.cardBody}>
          3 meetups nearby. Head to the PaceMeet tab to join a run or lift session.
        </Text>
        <View style={styles.spacer} />
        <PrimaryButton
          label="Open PaceMeet"
          onPress={() => track('open_pacemeet_from_home')}
        />
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
  cardTitle: {
    fontFamily: font.display,
    fontSize: 14,
    textTransform: 'uppercase',
    letterSpacing: 1.3,
    color: colors.umber,
  },
  cardHeadline: {
    fontFamily: font.display,
    fontSize: 20,
    color: colors.night,
    marginTop: spacing.xs,
  },
  cardBody: {
    fontFamily: font.body,
    color: colors.umber,
    marginTop: spacing.sm,
  },
  row: {
    flexDirection: 'row',
    gap: spacing.sm,
    marginTop: spacing.sm,
  },
  cardTitleDark: {
    fontFamily: font.display,
    fontSize: 14,
    textTransform: 'uppercase',
    letterSpacing: 1.3,
    color: colors.cream,
  },
  cardHeadlineDark: {
    fontFamily: font.display,
    fontSize: 20,
    color: colors.cream,
    marginTop: spacing.xs,
  },
  cardBodyDark: {
    fontFamily: font.body,
    color: colors.cream,
    marginTop: spacing.sm,
  },
  spacer: {
    height: spacing.sm,
  },
  divider: {
    height: 1,
    backgroundColor: 'rgba(255,255,255,0.3)',
    marginVertical: spacing.sm,
  },
  secondaryText: {
    fontFamily: font.display,
    color: colors.cream,
    marginTop: spacing.xs,
  },
});
