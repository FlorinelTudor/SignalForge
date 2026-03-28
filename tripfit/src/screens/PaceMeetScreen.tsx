import React from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { Card } from '../components/Card';
import { PrimaryButton } from '../components/PrimaryButton';
import { meetups } from '../data/meetups';
import { track } from '../utils/analytics';
import { colors, font, spacing } from '../utils/theme';

export function PaceMeetScreen() {
  return (
    <View style={styles.container}>
      <Text style={styles.title}>PaceMeet</Text>
      <Text style={styles.subtitle}>
        Meet nearby travelers for a run or lift session based on your location.
      </Text>

      <Card>
        <Text style={styles.cardHeadline}>Enable location</Text>
        <Text style={styles.cardBody}>
          We use your location to surface safe, nearby meetups while you travel.
        </Text>
        <View style={styles.spacer} />
        <PrimaryButton label="Allow location" onPress={() => track('location_request')} />
      </Card>

      <Card>
        <Text style={styles.cardHeadline}>Host a meetup</Text>
        <Text style={styles.cardBody}>
          Create a quick run or lift session and invite other TripFit travelers.
        </Text>
        <View style={styles.spacer} />
        <PrimaryButton label="Create meetup" onPress={() => track('meetup_create_tap')} />
      </Card>

      {meetups.map((meetup) => (
        <Card key={meetup.id}>
          <Text style={styles.cardHeadline}>{meetup.title}</Text>
          <Text style={styles.cardBody}>{meetup.time}</Text>
          <Text style={styles.cardBody}>{meetup.location}</Text>
          <View style={styles.row}>
            <Text style={styles.pill}>{meetup.type.toUpperCase()}</Text>
            <Text style={styles.pill}>{meetup.distanceKm} km away</Text>
            <Text style={styles.pill}>{meetup.spots} spots</Text>
          </View>
          <Text style={styles.cardBody}>{meetup.vibe}</Text>
          <View style={styles.spacer} />
          <Pressable
            style={styles.joinButton}
            onPress={() => track('meetup_join', { id: meetup.id })}
          >
            <Text style={styles.joinText}>Join meetup</Text>
          </Pressable>
        </Card>
      ))}
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
  subtitle: {
    fontFamily: font.body,
    fontSize: 14,
    color: colors.umber,
  },
  cardHeadline: {
    fontFamily: font.display,
    fontSize: 18,
    color: colors.night,
  },
  cardBody: {
    fontFamily: font.body,
    color: colors.umber,
    marginTop: spacing.xs,
  },
  spacer: {
    height: spacing.sm,
  },
  row: {
    flexDirection: 'row',
    gap: spacing.sm,
    marginTop: spacing.sm,
    flexWrap: 'wrap',
  },
  pill: {
    fontFamily: font.body,
    fontSize: 12,
    color: colors.umber,
    backgroundColor: colors.fog,
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xs,
    borderRadius: 999,
  },
  joinButton: {
    borderRadius: 999,
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.lg,
    borderWidth: 1,
    borderColor: colors.umber,
    alignSelf: 'flex-start',
  },
  joinText: {
    fontFamily: font.display,
    color: colors.umber,
  },
});
