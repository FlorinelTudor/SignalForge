import React, { useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { Card } from '../components/Card';
import { PrimaryButton } from '../components/PrimaryButton';
import { Tag } from '../components/Tag';
import { workouts, Workout } from '../data/workouts';
import { track } from '../utils/analytics';
import { colors, font, spacing } from '../utils/theme';

type Props = {
  goal: 'run' | 'lift' | 'both';
};

export function WorkoutsScreen({ goal }: Props) {
  const [active, setActive] = useState<Workout | null>(null);
  const filtered = workouts.filter((w) => goal === 'both' || w.focus === goal);

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Workouts</Text>
      {filtered.map((workout) => (
        <Pressable
          key={workout.id}
          onPress={() => {
            setActive(workout);
            track('workout_open', { workoutId: workout.id });
          }}
        >
          <Card>
            <Text style={styles.cardHeadline}>{workout.title}</Text>
            <View style={styles.row}>
              <Tag label={`${workout.durationMin} min`} />
              <Tag label={workout.focus.toUpperCase()} />
              <Tag label={workout.equipment} />
            </View>
          </Card>
        </Pressable>
      ))}

      {active && (
        <Card tone="dark">
          <Text style={styles.detailTitle}>{active.title}</Text>
          {active.steps.map((step) => (
            <Text key={step} style={styles.detailText}>{`• ${step}`}</Text>
          ))}
          <View style={styles.detailActions}>
            <PrimaryButton
              label="Mark complete"
              onPress={() => track('workout_complete', { workoutId: active.id })}
            />
          </View>
          <Text style={styles.detailHint}>Tap another workout to switch.</Text>
        </Card>
      )}
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
  cardHeadline: {
    fontFamily: font.display,
    fontSize: 18,
    color: colors.night,
    marginBottom: spacing.sm,
  },
  row: {
    flexDirection: 'row',
    gap: spacing.sm,
  },
  detailTitle: {
    fontFamily: font.display,
    fontSize: 18,
    color: colors.cream,
    marginBottom: spacing.sm,
  },
  detailText: {
    fontFamily: font.body,
    color: colors.cream,
    marginBottom: spacing.xs,
  },
  detailHint: {
    fontFamily: font.body,
    color: 'rgba(255,255,255,0.7)',
    marginTop: spacing.sm,
  },
  detailActions: {
    marginTop: spacing.sm,
  },
});
