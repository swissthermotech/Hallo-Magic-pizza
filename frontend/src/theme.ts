// Design tokens for this app. Light theme only.Always modify the colors and theme to Dark, Light or Dark and Light according to the design guidelines.
//
// The keys match the "color" block of /app/design_guidelines.json. Fill the
// values from that file (or from the user's brand colors). Keep every key; do
// not add a second theme or colors file; do not write color literals in
// components.
//
// How the names work: a plain key is a background, and its `on` partner is the
// text or icon color that sits on top of it. Always use them as a pair.
//   <View style={{ backgroundColor: colors.brandPrimary }}>
//     <Text style={{ color: colors.onBrandPrimary }}>Continue</Text>
//   </View>
//
// Styling a screen or component: build the sheet with makeStyles so colors
// and layout live together and follow the active scheme:
//   const useStyles = makeStyles((colors) => ({
//     card: { backgroundColor: colors.surfaceSecondary, padding: 16 },
//     title: { color: colors.onSurfaceSecondary, fontSize: 16 },
//   }));
//   function Screen() {
//     const styles = useStyles();
//     return <View style={styles.card}><Text style={styles.title}>Hi</Text></View>;
//   }
// For color props that are not styles (icon color, placeholderTextColor,
// ActivityIndicator) read useTheme().colors inside the component.
// Never call StyleSheet.create with color values at module level; it cannot
// follow the scheme.
//
// To support dark mode later: add `dark` to `themes` with every key filled.
// Nothing else changes; the device setting takes over automatically.
// Feel free to add as many new colors as you need to support the design guidelines.

import { useMemo } from "react";
import { Appearance, StyleSheet, useColorScheme } from "react-native";

export type ColorScheme = "light" | "dark";

const light = {
  // ---------------------------------------------------------------------------
  // Surfaces: backgrounds, from the screen down to small fills.
  // Each `on` key is the text and icon color for that background.
  // ---------------------------------------------------------------------------
  surface: "#FDFBF7", // warm cream canvas
  onSurface: "#2B2521",
  surfaceSecondary: "#FFFFFF", // cards, sheets, list rows
  onSurfaceSecondary: "#2B2521",
  surfaceTertiary: "#F2EAE1", // input backgrounds, chips
  onSurfaceTertiary: "#3E352F",
  surfaceInverse: "#2B2521", // dark espresso, tooltips / scrims
  onSurfaceInverse: "#FDFBF7",
  muted: "#8F7D70",

  // Brand: tomato red, olive green, terracotta
  brand: "#E63946",
  onBrand: "#FFFFFF",
  brandPrimary: "#E63946",
  onBrandPrimary: "#FFFFFF",
  brandSecondary: "#556B2F",
  onBrandSecondary: "#FFFFFF",
  brandTertiary: "#E2725B",
  onBrandTertiary: "#FFFFFF",

  // Status
  success: "#556B2F",
  onSuccess: "#FFFFFF",
  warning: "#E2725B",
  onWarning: "#FFFFFF",
  error: "#D32F2F",
  onError: "#FFFFFF",
  info: "#8F7D70",
  onInfo: "#FFFFFF",

  // Lines
  border: "#EAE3D9",
  borderStrong: "#D4C9BD",
  divider: "#EAE3D9",

  // Extras used by this app
  brandSoft: "#FBE3E5", // light tomato tint for selected chips / badges
  successSoft: "#E6EBDA", // light olive tint
  warningSoft: "#FAE1DA", // light terracotta tint
  ticketPaper: "#FFFDF5",
  scrim: "rgba(43,37,33,0.7)",
  scrimTransparent: "rgba(43,37,33,0)",
  overlay: "rgba(43,37,33,0.45)",
};

export type ThemeColors = typeof light;

export const defaultScheme = "light" satisfies ColorScheme;

export const themes: { light: ThemeColors; dark?: ThemeColors } = { light };

// In-app theme toggle, only after `dark` exists in `themes`. Call
// setColorScheme("dark"), setColorScheme("light"), or setColorScheme(null) to
// follow the device. Every useTheme() consumer re-renders. Persisting the
// choice and re-applying it on launch is the toggle's job.
export function setColorScheme(scheme: ColorScheme | null) {
  Appearance.setColorScheme?.(scheme);
}

// Keep native surfaces (alerts, pickers, navigation chrome) on the schemes this
// app ships: light only forces light; once `dark` exists the device decides.
// Optional call because react-native-web does not implement it.
setColorScheme?.(themes.dark ? null : defaultScheme);

export function useTheme(): { scheme: ColorScheme; colors: ThemeColors } {
  const system = useColorScheme();
  const scheme: ColorScheme = system && themes[system] ? system : defaultScheme;
  return { scheme, colors: themes[scheme] ?? themes.light };
}

// Themed StyleSheet: returns a hook that builds the sheet from the active
// scheme's colors and memoizes it until the scheme changes.
export function makeStyles<T extends StyleSheet.NamedStyles<T> | StyleSheet.NamedStyles<any>>(
  factory: (colors: ThemeColors) => T & StyleSheet.NamedStyles<any>,
): () => T {
  return function useStyles(): T {
    const { colors } = useTheme();
    return useMemo(() => StyleSheet.create(factory(colors)), [colors]);
  };
}


