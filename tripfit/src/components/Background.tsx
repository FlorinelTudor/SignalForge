import React from 'react';
import { StyleSheet, View } from 'react-native';
import { colors } from '../utils/theme';

type Props = {
  children: React.ReactNode;
};

export function Background({ children }: Props) {
  return (
    <View style={styles.container}>
      <View style={styles.blobTop} />
      <View style={styles.blobBottom} />
      {children}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.sand,
  },
  blobTop: {
    position: 'absolute',
    width: 260,
    height: 260,
    borderRadius: 200,
    backgroundColor: colors.sky,
    opacity: 0.25,
    top: -80,
    right: -60,
  },
  blobBottom: {
    position: 'absolute',
    width: 320,
    height: 320,
    borderRadius: 240,
    backgroundColor: colors.clay,
    opacity: 0.18,
    bottom: -120,
    left: -80,
  },
});
