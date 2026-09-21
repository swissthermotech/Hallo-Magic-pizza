import React, { useState } from "react";
import { ActivityIndicator, Pressable, Switch, Text, View } from "react-native";
import { useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { KeyboardAwareScrollView } from "react-native-keyboard-controller";
import { Feather } from "@react-native-vector-icons/feather";
import { makeStyles, useTheme } from "@/src/theme";
import { statusLabel, useI18n } from "@/src/i18n";
import { useAuth } from "@/src/auth";
import { useMyAccountOrders } from "@/src/api";
import { chf, fmtTime, statusTone } from "@/src/format";
import { Badge, Button, Field, FONT_DISPLAY, FONT_TEXT, ScreenHeader, useToast } from "@/src/components/ui";

export default function AccountScreen() {
  const { ready, user } = useAuth();
  const styles = useStyles();
  const { colors } = useTheme();
  const { t } = useI18n();
  if (!ready) {
    return <View style={[styles.screen, styles.center]}><ActivityIndicator color={colors.brandPrimary} /></View>;
  }
  return (
    <View style={styles.screen}>
      <ScreenHeader title={t("account")} subtitle={user ? `${t("loggedInAs")} ${user.first_name}` : t("guestHint")} testID="account-title" />
      {user ? <Profile /> : <AuthForm />}
    </View>
  );
}

// ---------------------------------------------------------------------------
// Login / register
// ---------------------------------------------------------------------------
function AuthForm() {
  const styles = useStyles();
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const { t } = useI18n();
  const toast = useToast();
  const { login, register } = useAuth();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [f, setF] = useState({ first_name: "", last_name: "", phone: "", email: "", password: "" });
  const [marketing, setMarketing] = useState(false); // optional, unchecked by default
  const [busy, setBusy] = useState(false);
  const set = (k: keyof typeof f) => (v: string) => setF((p) => ({ ...p, [k]: v }));

  const submit = async () => {
    if (!f.phone.trim() || f.password.length < 6 || (mode === "register" && !f.first_name.trim())) {
      toast.show(t("required"), "error");
      return;
    }
    setBusy(true);
    try {
      if (mode === "login") await login(f.phone.trim(), f.password);
      else await register({ first_name: f.first_name.trim(), last_name: f.last_name.trim(), phone: f.phone.trim(), email: f.email.trim() || undefined, password: f.password, marketing_consent: marketing });
      toast.show(`${t("welcome")} !`, "success");
    } catch (e: any) {
      toast.show(e?.message || "Erreur", "error");
    } finally {
      setBusy(false);
    }
  };

  return (
    <KeyboardAwareScrollView contentContainerStyle={{ padding: 16, gap: 14, paddingBottom: insets.bottom + 40 }} bottomOffset={40}>
      <View style={styles.segment}>
        <Pressable testID="auth-mode-login" onPress={() => setMode("login")} style={[styles.segBtn, mode === "login" && styles.segBtnActive]}><Text style={[styles.segText, mode === "login" && styles.segTextActive]}>{t("login")}</Text></Pressable>
        <Pressable testID="auth-mode-register" onPress={() => setMode("register")} style={[styles.segBtn, mode === "register" && styles.segBtnActive]}><Text style={[styles.segText, mode === "register" && styles.segTextActive]}>{t("register")}</Text></Pressable>
      </View>
      {mode === "register" ? (
        <View style={styles.two}>
          <Field label={`${t("firstName")} *`} value={f.first_name} onChangeText={set("first_name")} style={{ flex: 1 }} autoCapitalize="words" testID="auth-first-name" />
          <Field label={t("lastName")} value={f.last_name} onChangeText={set("last_name")} style={{ flex: 1 }} autoCapitalize="words" testID="auth-last-name" />
        </View>
      ) : null}
      <Field label={`${t("phone")} *`} value={f.phone} onChangeText={set("phone")} keyboardType="phone-pad" placeholder="079 123 45 67" testID="auth-phone" />
      {mode === "register" ? <Field label={t("email")} value={f.email} onChangeText={set("email")} keyboardType="email-address" autoCapitalize="none" testID="auth-email" /> : null}
      <Field label={`${t("password")} *`} value={f.password} onChangeText={set("password")} secureTextEntry autoCapitalize="none" placeholder={mode === "register" ? t("passwordHint") : undefined} testID="auth-password" />
      {mode === "register" ? (
        <Pressable testID="auth-marketing-checkbox" onPress={() => setMarketing((v) => !v)} style={styles.checkRow} accessibilityRole="checkbox" accessibilityState={{ checked: marketing }}>
          <View style={[styles.checkbox, marketing && styles.checkboxOn]}>{marketing ? <Feather name="check" size={16} color={colors.onBrandPrimary} /> : null}</View>
          <Text style={styles.checkText} testID="auth-marketing-text">{t("marketingConsent")}</Text>
        </Pressable>
      ) : null}
      <Button title={mode === "login" ? t("login") : t("register")} size="lg" icon={mode === "login" ? "log-in" : "user-plus"} loading={busy} onPress={submit} testID="auth-submit" />
      <Pressable testID="auth-switch-mode" onPress={() => setMode(mode === "login" ? "register" : "login")} style={{ paddingVertical: 8 }}>
        <Text style={styles.link}>{mode === "login" ? `${t("noAccountYet")} ${t("register")}` : `${t("alreadyAccount")} ${t("login")}`}</Text>
      </Pressable>
      <Text style={styles.hint}>{t("guestHint")}</Text>
    </KeyboardAwareScrollView>
  );
}

// ---------------------------------------------------------------------------
// Profile: details, addresses, order history
// ---------------------------------------------------------------------------
function Profile() {
  const styles = useStyles();
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const { t, tx } = useI18n();
  const toast = useToast();
  const { user, logout, updateProfile, deleteAddress, setMarketing } = useAuth();
  const { data: orders } = useMyAccountOrders(true);
  const u = user!;
  const [edit, setEdit] = useState(false);
  const [f, setF] = useState({ first_name: u.first_name, last_name: u.last_name, phone: u.phone, email: u.email || "" });
  const [busy, setBusy] = useState(false);
  const set = (k: keyof typeof f) => (v: string) => setF((p) => ({ ...p, [k]: v }));

  const saveProfile = async () => {
    setBusy(true);
    try {
      await updateProfile({ first_name: f.first_name.trim(), last_name: f.last_name.trim(), phone: f.phone.trim(), email: f.email.trim() || undefined });
      toast.show(t("saved"), "success");
      setEdit(false);
    } catch (e: any) {
      toast.show(e?.message || "Erreur", "error");
    } finally {
      setBusy(false);
    }
  };

  return (
    <KeyboardAwareScrollView contentContainerStyle={{ padding: 16, gap: 20, paddingBottom: insets.bottom + 40 }} bottomOffset={40}>
      {/* Profile */}
      <View>
        <View style={styles.sectionRow}>
          <Text style={styles.sectionTitle}>{t("profile")}</Text>
          <Pressable testID="profile-edit-toggle" onPress={() => setEdit((v) => !v)}><Text style={styles.link}>{edit ? t("close") : t("edit")}</Text></Pressable>
        </View>
        <View style={styles.card}>
          {edit ? (
            <View style={{ gap: 12 }}>
              <View style={styles.two}>
                <Field label={`${t("firstName")} *`} value={f.first_name} onChangeText={set("first_name")} style={{ flex: 1 }} testID="profile-first-name" />
                <Field label={t("lastName")} value={f.last_name} onChangeText={set("last_name")} style={{ flex: 1 }} testID="profile-last-name" />
              </View>
              <Field label={`${t("phone")} *`} value={f.phone} onChangeText={set("phone")} keyboardType="phone-pad" testID="profile-phone" />
              <Field label={t("email")} value={f.email} onChangeText={set("email")} keyboardType="email-address" autoCapitalize="none" testID="profile-email" />
              <Button title={t("save")} icon="check" loading={busy} onPress={saveProfile} testID="profile-save" />
            </View>
          ) : (
            <>
              <Text style={styles.name} testID="profile-name">{u.first_name} {u.last_name}</Text>
              <Text style={styles.info} testID="profile-phone-text">{u.phone}</Text>
              {u.email ? <Text style={styles.info}>{u.email}</Text> : null}
            </>
          )}
        </View>
      </View>

      {/* Addresses */}
      <View>
        <View style={styles.sectionRow}>
          <Text style={styles.sectionTitle}>{t("savedAddresses")}</Text>
          <Pressable testID="address-add" onPress={() => router.push("/account/address")}><Text style={styles.link}>+ {t("addAddress")}</Text></Pressable>
        </View>
        <View style={[styles.card, { padding: 0 }]}>
          {u.addresses.length === 0 ? <Text style={[styles.hint, { padding: 16 }]}>{t("noAddresses")}</Text> : null}
          {u.addresses.map((a, i) => (
            <View key={a.id} style={[styles.addrRow, i > 0 && styles.sep]} testID={`address-row-${a.id}`}>
              <View style={styles.rowIcon}><Feather name="map-pin" size={16} color={colors.brandPrimary} /></View>
              <View style={{ flex: 1 }}>
                {a.label ? <Text style={styles.addrLabel}>{a.label}</Text> : null}
                <Text style={styles.info}>{a.street} {a.number}, {a.npa} {a.city}</Text>
                {a.instructions ? <Text style={styles.hint}>{a.instructions}</Text> : null}
              </View>
              <Pressable testID={`address-edit-${a.id}`} onPress={() => router.push({ pathname: "/account/address", params: { id: a.id } })} style={styles.iconBtn}><Feather name="edit-2" size={16} color={colors.onSurface} /></Pressable>
              <Pressable testID={`address-delete-${a.id}`} onPress={() => deleteAddress(a.id).catch((e) => toast.show(e.message, "error"))} style={styles.iconBtn}><Feather name="trash-2" size={16} color={colors.error} /></Pressable>
            </View>
          ))}
        </View>
      </View>

      {/* Marketing preference – account holders can opt in or withdraw at any time */}
      <View>
        <Text style={[styles.sectionTitle, { marginBottom: 8 }]}>{t("marketingTitle")}</Text>
        <View style={[styles.card, { flexDirection: "row", alignItems: "center", gap: 12 }]}>
          <Text style={[styles.info, { flex: 1 }]} testID="profile-marketing-text">{t("marketingConsent")}</Text>
          <Switch testID="profile-marketing-switch" value={!!u.marketing_consent} disabled={busy} onValueChange={(v) => { setBusy(true); setMarketing(v).then(() => toast.show(v ? t("marketingOn") : t("marketingOff"), "success")).catch((e) => toast.show(e.message, "error")).finally(() => setBusy(false)); }} trackColor={{ true: colors.success, false: colors.borderStrong }} thumbColor={colors.surfaceSecondary} />
        </View>
      </View>

      {/* Order history */}
      <View>
        <Text style={[styles.sectionTitle, { marginBottom: 8 }]}>{t("orderHistory")}</Text>
        <View style={{ gap: 10 }}>
          {!orders || orders.length === 0 ? <View style={styles.card}><Text style={styles.hint}>{t("noHistory")}</Text></View> : null}
          {(orders ?? []).map((o) => (
            <Pressable key={o.id} testID={`history-order-${o.id}`} onPress={() => router.push({ pathname: "/order/[id]", params: { id: o.id } })} style={({ pressed }) => [styles.card, pressed && { opacity: 0.9 }]}>
              <View style={styles.sectionRow}>
                <Text style={styles.num}>#{o.order_number}</Text>
                <Badge label={statusLabel(o.status, o.type, t)} tone={statusTone(o.status)} />
              </View>
              <Text style={styles.hint}>{o.type === "pickup" ? t("pickup") : t("delivery")} · {fmtTime(o.created_at)}</Text>
              <Text style={styles.info} numberOfLines={2}>{o.items.map((i) => `${i.quantity}x ${tx(i.name)}`).join(", ")}</Text>
              <Text style={styles.total}>{chf(o.total)}</Text>
            </Pressable>
          ))}
        </View>
      </View>

      <Button title={t("logout")} variant="outline" icon="log-out" onPress={() => logout().then(() => router.back())} testID="auth-logout" />
    </KeyboardAwareScrollView>
  );
}

const useStyles = makeStyles((colors) => ({
  screen: { flex: 1, backgroundColor: colors.surface },
  center: { alignItems: "center", justifyContent: "center" },
  segment: { flexDirection: "row", backgroundColor: colors.surfaceTertiary, borderRadius: 14, padding: 4, gap: 4 },
  segBtn: { flex: 1, height: 44, borderRadius: 11, alignItems: "center", justifyContent: "center" },
  segBtnActive: { backgroundColor: colors.surfaceInverse },
  segText: { fontFamily: FONT_TEXT, fontSize: 14, fontWeight: "800", color: colors.onSurface },
  segTextActive: { color: colors.onSurfaceInverse },
  two: { flexDirection: "row", gap: 10 },
  link: { fontFamily: FONT_TEXT, fontSize: 14, fontWeight: "700", color: colors.brandPrimary },
  hint: { fontFamily: FONT_TEXT, fontSize: 13, color: colors.muted },
  sectionRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: 8 },
  sectionTitle: { fontFamily: FONT_DISPLAY, fontSize: 20, color: colors.onSurface },
  card: { backgroundColor: colors.surfaceSecondary, borderRadius: 16, borderWidth: 1, borderColor: colors.border, padding: 16, gap: 4 },
  name: { fontFamily: FONT_TEXT, fontSize: 18, fontWeight: "800", color: colors.onSurface },
  info: { fontFamily: FONT_TEXT, fontSize: 14, color: colors.onSurfaceSecondary, lineHeight: 20 },
  addrRow: { flexDirection: "row", alignItems: "center", gap: 10, padding: 14 },
  sep: { borderTopWidth: 1, borderTopColor: colors.divider },
  rowIcon: { width: 32, height: 32, borderRadius: 10, backgroundColor: colors.brandSoft, alignItems: "center", justifyContent: "center" },
  addrLabel: { fontFamily: FONT_TEXT, fontSize: 14, fontWeight: "800", color: colors.onSurface },
  iconBtn: { width: 40, height: 40, borderRadius: 20, alignItems: "center", justifyContent: "center", backgroundColor: colors.surfaceTertiary },
  num: { fontFamily: FONT_DISPLAY, fontSize: 20, color: colors.onSurface },
  total: { fontFamily: FONT_TEXT, fontSize: 15, fontWeight: "800", color: colors.onSurface, marginTop: 4 },
  checkRow: { flexDirection: "row", gap: 12, alignItems: "center", paddingVertical: 4 },
  checkbox: { width: 26, height: 26, borderRadius: 7, borderWidth: 2, borderColor: colors.borderStrong, alignItems: "center", justifyContent: "center" },
  checkboxOn: { backgroundColor: colors.brandPrimary, borderColor: colors.brandPrimary },
  checkText: { fontFamily: FONT_TEXT, fontSize: 14, color: colors.onSurface, flex: 1 },
}));
