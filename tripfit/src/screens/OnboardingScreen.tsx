import React, { useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { Card } from '../components/Card';
import { PrimaryButton } from '../components/PrimaryButton';
import { colors, font, radius, spacing } from '../utils/theme';
import { Profile, TripLength, TripType } from '../utils/pricing';
import { track } from '../utils/analytics';

type Props = {
  onComplete: (profile: Profile) => void;
};

const tripLengths: { label: string; value: TripLength }[] = [
  { label: '1-7 days', value: '1-7' },
  { label: '8-14 days', value: '8-14' },
  { label: '15+ days', value: '15+' },
];

const tripTypes: { label: string; value: TripType }[] = [
  { label: 'Business', value: 'business' },
  { label: 'Leisure', value: 'leisure' },
  { label: 'Frequent traveler', value: 'frequent' },
];

const goals: { label: string; value: Profile['goal'] }[] = [
  { label: 'Run', value: 'run' },
  { label: 'Lift', value: 'lift' },
  { label: 'Both', value: 'both' },
];

export function OnboardingScreen({ onComplete }: Props) {
  const [tripLength, setTripLength] = useState<TripLength>('1-7');
  const [tripType, setTripType] = useState<TripType>('leisure');
  const [goal, setGoal] = useState<Profile['goal']>('run');

  const handleContinue = () => {
    const profile: Profile = { tripLength, tripType, goal };
    track('onboarding_complete', profile);
    onComplete(profile);
  };

  return (
    <ScrollView contentContainerStyle={styles.container}>
      <Text style={styles.kicker}>TripFit</Text>
      <Text style={styles.title}>Build a travel-proof routine.</Text>
      <Text style={styles.subtitle}>
        Answer a few questions so we can tune your trip plan and pricing options.
      </Text>

      <Card>
        <Text style={styles.sectionTitle}>How long is your trip?</Text>
        <View style={styles.rowWrap}>
          {tripLengths.map((item) => (
            <Pressable
              key={item.value}
              onPress={() => setTripLength(item.value)}
              style={[styles.choice, tripLength === item.value && styles.choiceActive]}
            >
              <Text style={[styles.choiceText, tripLength === item.value && styles.choiceTextActive]}>
                {item.label}
              </Text>
            </Pressable>
          ))}
        </View>
      </Card>

      <Card>
        <Text style={styles.sectionTitle}>What type of travel is it?</Text>
        <View style={styles.rowWrap}>
          {tripTypes.map((item) => (
            <Pressable
              key={item.value}
              onPress={() => setTripType(item.value)}
              style={[styles.choice, tripType === item.value && styles.choiceActive]}
            >
              <Text style={[styles.choiceText, tripType === item.value && styles.choiceTextActive]}>
                {item.label}
              </Text>
            </Pressable>
          ))}
        </View>
      </Card>

      <Card>
        <Text style={styles.sectionTitle}>Focus for this trip</Text>
        <View style={styles.rowWrap}>
          {goals.map((item) => (
            <Pressable
              key={item.value}
              onPress={() => setGoal(item.value)}
              style={[styles.choice, goal === item.value && styles.choiceActive]}
            >
              <Text style={[styles.choiceText, goal === item.value && styles.choiceTextActive]}>
                {item.label}
              </Text>
            </Pressable>
          ))}
        </View>
      </Card>

      <PrimaryButton label="Create my trip plan" onPress={handleContinue} />
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    padding: spacing.lg,
    gap: spacing.md,
  },
  kicker: {
    fontFamily: font.display,
    fontSize: 18,
    color: colors.umber,
    letterSpacing: 2,
    textTransform: 'uppercase',
  },
  title: {
    fontFamily: font.display,
    fontSize: 28,
    color: colors.night,
  },
  subtitle: {
    fontFamily: font.body,
    fontSize: 15,
    color: colors.umber,
  },
  sectionTitle: {
    fontFamily: font.display,
    fontSize: 16,
    marginBottom: spacing.sm,
    color: colors.night,
  },
  rowWrap: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.sm,
  },
  choice: {
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.fog,
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.md,
    backgroundColor: colors.sand,
  },
  choiceActive: {
    backgroundColor: colors.umber,
    borderColor: colors.umber,
  },
  choiceText: {
    fontFamily: font.body,
    color: colors.umber,
  },
  choiceTextActive: {
    color: colors.cream,
    fontFamily: font.display,
  },
});
