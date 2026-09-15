import React, { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import { ActivityIndicator, Pressable, Text, TextInput, View, type TextInputProps, type ViewStyle } from "react-native";
import { Feather } from "@react-native-vector-icons/feather";
import * as Haptics from "expo-haptics";
import Animated, { FadeInDown, FadeOutDown } from "react-native-reanimated";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useRouter } from "expo-router";
import { makeStyles, useTheme } from "@/src/theme";

export const FONT_DISPLAY = "PlayfairDisplay";
export const FONT_TEXT = "DMSans";

// ---------------------------------------------------------------------------
// Button
// ---------------------------------------------------------------------------
type Variant = "primary" | "secondary" | "outline" | "ghost" | "danger" | "success";
interface ButtonProps {
  title: string;
  onPress?: () => void;
  variant?: Variant;
  size?: "sm" | "md" | "lg" | "xl";
  icon?: React.ComponentProps<typeof Feather>["name"];
  disabled?: boolean;
  loading?: boolean;
  style?: ViewStyle;
  testID?: string;
}

export function Button({ title, onPress, variant = "primary", size = "md", icon, disabled, loading, style, testID }: ButtonProps) {
  const styles = useBtnStyles();
  const { colors } = useTheme();
  const bg = {
    primary: colors.brandPrimary,
    secondary: colors.surfaceTertiary,
    outline: "transparent",
    ghost: "transparent",
    danger: colors.error,
    success: colors.success,
  }[variant];
  const fg = {
    primary: colors.onBrandPrimary,
    secondary: colors.onSurfaceTertiary,
    outline: colors.onSurface,
    ghost: colors.brandPrimary,
    danger: colors.onError,
    success: colors.onSuccess,
  }[variant];
  const h = { sm: 40, md: 48, lg: 56, xl: 72 }[size];
  const fs = { sm: 14, md: 16, lg: 17, xl: 22 }[size];
  return (
    <Pressable
      testID={testID}
      disabled={disabled || loading}
      onPress={onPress}
      style={({ pressed }) => [
        styles.base,
        { backgroundColor: bg, height: h, opacity: disabled ? 0.5 : pressed ? 0.85 : 1, transform: [{ scale: pressed ? 0.98 : 1 }] },
        variant === "outline" && styles.outline,
        style,
      ]}
    >
      {loading ? (
        <ActivityIndicator color={fg} />
      ) : (
        <>
          {icon ? <Feather name={icon} size={fs + 2} color={fg} /> : null}
          <Text style={[styles.label, { color: fg, fontSize: fs }]}>{title}</Text>
        </>
      )}
    </Pressable>
  );
}

const useBtnStyles = makeStyles((colors) => ({
  base: { flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 8, borderRadius: 12, paddingHorizontal: 16 },
  outline: { borderWidth: 1.5, borderColor: colors.borderStrong },
  label: { fontFamily: FONT_TEXT, fontWeight: "700", letterSpacing: 0.2 },
}));

// ---------------------------------------------------------------------------
// Quantity stepper
// ---------------------------------------------------------------------------
export function Stepper({ value, onChange, min = 1, max = 20, size = 36, testID }: { value: number; onChange: (v: number) => void; min?: number; max?: number; size?: number; testID?: string }) {
  const styles = useStepperStyles();
  const { colors } = useTheme();
  const bump = (d: number) => {
    const nv = Math.max(min, Math.min(max, value + d));
    if (nv !== value) {
      Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light).catch(() => {});
      onChange(nv);
    }
  };
  return (
    <View style={styles.row} testID={testID}>
      <Pressable testID={testID ? `${testID}-minus` : undefined} onPress={() => bump(-1)} style={[styles.btn, { width: size, height: size, borderRadius: size / 2 }]} hitSlop={6}>
        <Feather name="minus" size={16} color={colors.onSurface} />
      </Pressable>
      <Text style={styles.value} testID={testID ? `${testID}-value` : undefined}>{value}</Text>
      <Pressable testID={testID ? `${testID}-plus` : undefined} onPress={() => bump(1)} style={[styles.btn, styles.btnPlus, { width: size, height: size, borderRadius: size / 2 }]} hitSlop={6}>
        <Feather name="plus" size={16} color={colors.onBrandPrimary} />
      </Pressable>
    </View>
  );
}
const useStepperStyles = makeStyles((colors) => ({
  row: { flexDirection: "row", alignItems: "center", gap: 12 },
  btn: { alignItems: "center", justifyContent: "center", backgroundColor: colors.surfaceTertiary },
  btnPlus: { backgroundColor: colors.brandPrimary },
  value: { fontFamily: FONT_TEXT, fontSize: 17, fontWeight: "700", minWidth: 20, textAlign: "center", color: colors.onSurface },
}));

// ---------------------------------------------------------------------------
// Chip
// ---------------------------------------------------------------------------
export function Chip({ label, selected, onPress, testID, tone = "brand" }: { label: string; selected?: boolean; onPress?: () => void; testID?: string; tone?: "brand" | "danger" }) {
  const styles = useChipStyles();
  return (
    <Pressable
      testID={testID}
      onPress={onPress}
      style={[styles.chip, selected && (tone === "danger" ? styles.chipDanger : styles.chipSelected)]}
    >
      <Text style={[styles.label, selected && (tone === "danger" ? styles.labelDanger : styles.labelSelected)]} numberOfLines={1}>
        {label}
      </Text>
    </Pressable>
  );
}
const useChipStyles = makeStyles((colors) => ({
  chip: { height: 36, paddingHorizontal: 14, borderRadius: 999, backgroundColor: colors.surfaceSecondary, borderWidth: 1, borderColor: colors.border, justifyContent: "center", flexShrink: 0 },
  chipSelected: { backgroundColor: colors.surfaceInverse, borderColor: colors.surfaceInverse },
  chipDanger: { backgroundColor: colors.brandSoft, borderColor: colors.brandPrimary },
  label: { fontFamily: FONT_TEXT, fontSize: 14, fontWeight: "600", color: colors.onSurface },
  labelSelected: { color: colors.onSurfaceInverse },
  labelDanger: { color: colors.brandPrimary, textDecorationLine: "line-through" },
}));

// ---------------------------------------------------------------------------
// Field (label + input)
// ---------------------------------------------------------------------------
export function Field({ label, style, testID, ...props }: TextInputProps & { label: string; testID?: string; style?: ViewStyle }) {
  const styles = useFieldStyles();
  const { colors } = useTheme();
  return (
    <View style={[styles.wrap, style]}>
      <Text style={styles.label}>{label}</Text>
      <TextInput testID={testID} placeholderTextColor={colors.muted} style={[styles.input, props.multiline && styles.multiline]} {...props} />
    </View>
  );
}
const useFieldStyles = makeStyles((colors) => ({
  wrap: { gap: 6 },
  label: { fontFamily: FONT_TEXT, fontSize: 13, fontWeight: "600", color: colors.muted, textTransform: "uppercase", letterSpacing: 0.6 },
  input: { height: 48, borderRadius: 12, backgroundColor: colors.surfaceSecondary, borderWidth: 1, borderColor: colors.border, paddingHorizontal: 14, fontFamily: FONT_TEXT, fontSize: 16, color: colors.onSurface },
  multiline: { height: 88, paddingTop: 12, textAlignVertical: "top" },
}));

// ---------------------------------------------------------------------------
// Section title
// ---------------------------------------------------------------------------
export function SectionTitle({ title, right, testID }: { title: string; right?: React.ReactNode; testID?: string }) {
  const styles = useSectionStyles();
  return (
    <View style={styles.row}>
      <Text style={styles.title} testID={testID}>{title}</Text>
      {right}
    </View>
  );
}
const useSectionStyles = makeStyles((colors) => ({
  row: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", marginBottom: 12 },
  title: { fontFamily: FONT_DISPLAY, fontSize: 22, color: colors.onSurface },
}));

// ---------------------------------------------------------------------------
// Screen header (sticky, safe-area aware)
// ---------------------------------------------------------------------------
export function ScreenHeader({ title, subtitle, right, back = true, testID }: { title: string; subtitle?: string; right?: React.ReactNode; back?: boolean; testID?: string }) {
  const styles = useHeaderStyles();
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const router = useRouter();
  return (
    <View style={[styles.wrap, { paddingTop: insets.top + 8 }]}>
      {back ? (
        <Pressable testID="header-back-button" onPress={() => (router.canGoBack() ? router.back() : router.replace("/"))} style={styles.back} hitSlop={8}>
          <Feather name="arrow-left" size={22} color={colors.onSurface} />
        </Pressable>
      ) : null}
      <View style={{ flex: 1 }}>
        <Text style={styles.title} testID={testID} numberOfLines={1}>{title}</Text>
        {subtitle ? <Text style={styles.subtitle} numberOfLines={1}>{subtitle}</Text> : null}
      </View>
      {right}
    </View>
  );
}
const useHeaderStyles = makeStyles((colors) => ({
  wrap: { flexDirection: "row", alignItems: "center", gap: 12, paddingHorizontal: 16, paddingBottom: 12, backgroundColor: colors.surface, borderBottomWidth: 1, borderBottomColor: colors.border },
  back: { width: 44, height: 44, borderRadius: 22, alignItems: "center", justifyContent: "center", backgroundColor: colors.surfaceSecondary, borderWidth: 1, borderColor: colors.border },
  title: { fontFamily: FONT_DISPLAY, fontSize: 22, color: colors.onSurface },
  subtitle: { fontFamily: FONT_TEXT, fontSize: 13, color: colors.muted, marginTop: 2 },
}));

// ---------------------------------------------------------------------------
// Toast
// ---------------------------------------------------------------------------
interface ToastCtx {
  show: (msg: string, tone?: "success" | "error" | "info") => void;
}
const ToastContext = createContext<ToastCtx>({ show: () => {} });
export const useToast = () => useContext(ToastContext);

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toast, setToast] = useState<{ msg: string; tone: "success" | "error" | "info"; key: number } | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const styles = useToastStyles();
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const show = useCallback((msg: string, tone: "success" | "error" | "info" = "info") => {
    setToast({ msg, tone, key: Date.now() });
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => setToast(null), 2600);
  }, []);
  useEffect(() => () => { if (timer.current) clearTimeout(timer.current); }, []);
  const bg = toast?.tone === "error" ? colors.error : toast?.tone === "success" ? colors.success : colors.surfaceInverse;
  return (
    <ToastContext.Provider value={{ show }}>
      {children}
      {toast ? (
        <Animated.View key={toast.key} entering={FadeInDown} exiting={FadeOutDown} pointerEvents="none" style={[styles.toast, { bottom: insets.bottom + 90, backgroundColor: bg }]} testID="toast">
          <Text style={styles.text}>{toast.msg}</Text>
        </Animated.View>
      ) : null}
    </ToastContext.Provider>
  );
}
const useToastStyles = makeStyles((colors) => ({
  toast: { position: "absolute", left: 16, right: 16, borderRadius: 14, paddingVertical: 14, paddingHorizontal: 18, alignItems: "center", shadowColor: colors.surfaceInverse, shadowOpacity: 0.2, shadowRadius: 12, shadowOffset: { width: 0, height: 6 }, elevation: 6 },
  text: { fontFamily: FONT_TEXT, color: colors.onSurfaceInverse, fontSize: 15, fontWeight: "600", textAlign: "center" },
}));

// ---------------------------------------------------------------------------
// Badge
// ---------------------------------------------------------------------------
export function Badge({ label, tone = "neutral", testID }: { label: string; tone?: "neutral" | "brand" | "success" | "warning" | "error" | "inverse"; testID?: string }) {
  const { colors } = useTheme();
  const map = {
    neutral: [colors.surfaceTertiary, colors.onSurfaceTertiary],
    brand: [colors.brandSoft, colors.brandPrimary],
    success: [colors.successSoft, colors.success],
    warning: [colors.warningSoft, colors.warning],
    error: [colors.error, colors.onError],
    inverse: [colors.surfaceInverse, colors.onSurfaceInverse],
  }[tone];
  return (
    <View testID={testID} style={{ backgroundColor: map[0], paddingHorizontal: 10, height: 26, borderRadius: 999, justifyContent: "center", alignSelf: "flex-start" }}>
      <Text style={{ fontFamily: FONT_TEXT, fontSize: 12, fontWeight: "700", color: map[1], letterSpacing: 0.4 }}>{label}</Text>
    </View>
  );
}

export function Empty({ icon, title, hint, action }: { icon: React.ComponentProps<typeof Feather>["name"]; title: string; hint?: string; action?: React.ReactNode }) {
  const { colors } = useTheme();
  return (
    <View style={{ alignItems: "center", paddingVertical: 48, paddingHorizontal: 24, gap: 10 }}>
      <View style={{ width: 72, height: 72, borderRadius: 36, backgroundColor: colors.surfaceTertiary, alignItems: "center", justifyContent: "center", marginBottom: 6 }}>
        <Feather name={icon} size={30} color={colors.muted} />
      </View>
      <Text style={{ fontFamily: FONT_DISPLAY, fontSize: 22, color: colors.onSurface, textAlign: "center" }}>{title}</Text>
      {hint ? <Text style={{ fontFamily: FONT_TEXT, fontSize: 15, color: colors.muted, textAlign: "center", lineHeight: 22 }}>{hint}</Text> : null}
      {action ? <View style={{ marginTop: 12 }}>{action}</View> : null}
    </View>
  );
}
