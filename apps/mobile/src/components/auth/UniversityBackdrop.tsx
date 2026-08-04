import { StyleSheet, View } from 'react-native';

import { lightColors, radii } from '../../theme';

const COLUMNS = Array.from({ length: 7 }, (_, index) => index);

export function UniversityBackdrop() {
  return (
    <View pointerEvents="none" style={StyleSheet.absoluteFill}>
      <View style={styles.sky} />
      <View style={styles.lowerSky} />
      <View style={styles.glow} />
      <View style={styles.building}>
        <View style={styles.roof} />
        <View style={styles.flag} />
        <View style={styles.columns}>
          {COLUMNS.map((column) => (
            <View key={column} style={styles.column} />
          ))}
        </View>
      </View>
      <View style={styles.scrim} />
    </View>
  );
}

const styles = StyleSheet.create({
  sky: {
    position: 'absolute',
    top: 0,
    right: 0,
    bottom: 0,
    left: 0,
    backgroundColor: '#1E4E9C',
  },
  lowerSky: {
    position: 'absolute',
    right: 0,
    bottom: 0,
    left: 0,
    height: '60%',
    backgroundColor: '#0F2C5C',
  },
  glow: {
    position: 'absolute',
    top: -80,
    right: -70,
    width: 250,
    height: 250,
    borderRadius: radii.full,
    backgroundColor: 'rgba(143, 176, 255, 0.12)',
  },
  building: {
    position: 'absolute',
    top: '15%',
    right: '7%',
    left: '7%',
    height: 260,
    alignItems: 'center',
    justifyContent: 'flex-end',
    opacity: 0.42,
  },
  roof: {
    position: 'absolute',
    top: 18,
    width: 230,
    height: 230,
    transform: [{ rotate: '45deg' }],
    borderRadius: radii.small,
    backgroundColor: lightColors.primaryInteraction,
  },
  flag: {
    position: 'absolute',
    top: 0,
    width: 50,
    height: 14,
    backgroundColor: lightColors.accent,
  },
  columns: {
    width: '100%',
    height: 150,
    flexDirection: 'row',
    alignItems: 'stretch',
    justifyContent: 'space-evenly',
    paddingHorizontal: 24,
    paddingTop: 18,
    borderRadius: radii.small,
    backgroundColor: lightColors.primaryInteraction,
  },
  column: {
    width: 18,
    backgroundColor: lightColors.primary,
  },
  scrim: {
    position: 'absolute',
    top: 0,
    right: 0,
    bottom: 0,
    left: 0,
    backgroundColor: 'rgba(7, 19, 43, 0.44)',
  },
});
