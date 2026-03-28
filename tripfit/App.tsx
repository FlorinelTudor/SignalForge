import React, { useState } from 'react';
import { SafeAreaView, StyleSheet, Text, Pressable, View } from 'react-native';
import { Background } from './src/components/Background';
import { HomeScreen } from './src/screens/HomeScreen';
import { OnboardingScreen } from './src/screens/OnboardingScreen';
import { PaceMeetScreen } from './src/screens/PaceMeetScreen';
import { ProfileScreen } from './src/screens/ProfileScreen';
import { WorkoutsScreen } from './src/screens/WorkoutsScreen';
import { Profile } from './src/utils/pricing';
import { colors, font, spacing } from './src/utils/theme';

const tabs = ['Plan', 'Workouts', 'PaceMeet', 'Profile'] as const;
type TabKey = (typeof tabs)[number];

export default function App() {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [tab, setTab] = useState<TabKey>('Plan');

  if (!profile) {
    return (
      <Background>
        <SafeAreaView style={styles.safe}>
          <OnboardingScreen
            onComplete={(next) => {
              setProfile(next);
              setTab('Plan');
            }}
          />
        </SafeAreaView>
      </Background>
    );
  }

  return (
    <Background>
      <SafeAreaView style={styles.safe}>
        <View style={styles.content}>
          {tab === 'Plan' && <HomeScreen profile={profile} />}
          {tab === 'Workouts' && <WorkoutsScreen goal={profile.goal} />}
          {tab === 'PaceMeet' && <PaceMeetScreen />}
          {tab === 'Profile' && (
            <ProfileScreen
              profile={profile}
              onReset={() => setProfile(null)}
            />
          )}
        </View>
        <View style={styles.tabBar}>
          {tabs.map((item) => (
            <Pressable
              key={item}
              onPress={() => setTab(item)}
              style={[styles.tab, tab === item && styles.tabActive]}
            >
              <Text style={[styles.tabText, tab === item && styles.tabTextActive]}>
                {item}
              </Text>
            </Pressable>
          ))}
        </View>
      </SafeAreaView>
    </Background>
  );
}

const styles = StyleSheet.create({
  safe: {
    flex: 1,
  },
  content: {
    flex: 1,
  },
  tabBar: {
    flexDirection: 'row',
    justifyContent: 'space-around',
    paddingVertical: spacing.sm,
    backgroundColor: colors.cream,
    borderTopWidth: 1,
    borderTopColor: colors.line,
  },
  tab: {
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.sm,
    borderRadius: 999,
    minHeight: 44,
    justifyContent: 'center',
  },
  tabActive: {
    backgroundColor: colors.umber,
  },
  tabText: {
    fontFamily: font.body,
    color: colors.umber,
    fontSize: 12,
    letterSpacing: 0.4,
  },
  tabTextActive: {
    color: colors.cream,
    fontFamily: font.display,
  },
});
