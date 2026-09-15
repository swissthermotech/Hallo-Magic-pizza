import React, { useState } from "react";
import { ActivityIndicator, Pressable, ScrollView, Text, TextInput, View } from "react-native";
import { useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { Feather } from "@react-native-vector-icons/feather";
import { makeStyles, useTheme } from "@/src/theme";
import { statusLabel, useI18n } from "@/src/i18n";
import { useCustomerSearch } from "@/src/api";
import { chf, fmtTime, statusTone } from "@/src/format";
import { Badge, Empty, FONT_DISPLAY, FONT_TEXT, ScreenHeader } from "@/src/components/ui";

/** Staff / phone-order lookup: find a customer (account or guest) by phone number. */
export default function StaffCustomersScreen() {
  const styles = useStyles();
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const { t } = useI18n();
  const [phone, setPhone] = useState("");
  const { data, isFetching } = useCustomerSearch(phone);
  const digits = phone.replace(/\D/g, "");

  return (
    <View style={styles.screen}>
      <ScreenHeader title={t("customers")} subtitle={t("searchByPhone")} testID="customers-title" />
      <View style={styles.searchWrap}>
        <Feather name="search" size={18} color={colors.muted} />
        <TextInput
          testID="customers-search-input"
          value={phone}
          onChangeText={setPhone}
          placeholder="079 123 45 67"
          placeholderTextColor={colors.muted}
          keyboardType="phone-pad"
          autoFocus
          style={styles.input}
        />
        {isFetching ? <ActivityIndicator color={colors.brandPrimary} /> : null}
      </View>
      <ScrollView contentContainerStyle={{ padding: 16, gap: 20, paddingBottom: insets.bottom + 24 }} keyboardShouldPersistTaps="handled">
        {digits.length < 3 ? <Text style={styles.hint}>{t("searchHint")}</Text> : null}
        {data && data.accounts.length === 0 && data.orders.length === 0 ? <Empty icon="user-x" title={t("noResults")} /> : null}

        {data && data.accounts.length > 0 ? (
          <View>
            <Text style={styles.section}>{t("accounts")} ({data.accounts.length})</Text>
            <View style={{ gap: 10 }}>
              {data.accounts.map((u) => (
                <View key={u.id} style={styles.card} testID={`customer-account-${u.id}`}>
                  <View style={styles.rowBetween}>
                    <Text style={styles.name}>{u.first_name} {u.last_name}</Text>
                    <Badge label="★ COMPTE" tone="brand" />
                  </View>
                  <Text style={styles.phone}>{u.phone}{u.email ? ` · ${u.email}` : ""}</Text>
                  {u.addresses.map((a) => (
                    <View key={a.id} style={styles.addr}>
                      <Feather name="map-pin" size={14} color={colors.brandPrimary} />
                      <Text style={styles.addrText}>{a.label ? `${a.label}: ` : ""}{a.street} {a.number}, {a.npa} {a.city}{a.instructions ? ` (${a.instructions})` : ""}</Text>
                    </View>
                  ))}
                </View>
              ))}
            </View>
          </View>
        ) : null}

        {data && data.orders.length > 0 ? (
          <View>
            <Text style={styles.section}>{t("pastOrders")} ({data.orders.length})</Text>
            <View style={{ gap: 10 }}>
              {data.orders.map((o) => (
                <Pressable key={o.id} testID={`customer-order-${o.id}`} onPress={() => router.push({ pathname: "/staff/ticket/[id]", params: { id: o.id } })} style={({ pressed }) => [styles.card, pressed && { opacity: 0.9 }]}>
                  <View style={styles.rowBetween}>
                    <Text style={styles.num}>#{o.order_number}</Text>
                    <View style={{ flexDirection: "row", gap: 6 }}>
                      {o.age_required ? <Badge label={`${o.age_required}+`} tone="warning" /> : null}
                      <Badge label={o.user_id ? "★" : t("guest").toUpperCase()} tone={o.user_id ? "brand" : "neutral"} />
                      <Badge label={statusLabel(o.status, o.type, t)} tone={statusTone(o.status)} />
                    </View>
                  </View>
                  <Text style={styles.phone}>{o.customer.first_name} {o.customer.last_name} · {o.customer.phone} · {fmtTime(o.created_at)}</Text>
                  {o.address ? <Text style={styles.addrText}>{o.address.street} {o.address.number}, {o.address.npa} {o.address.city}</Text> : null}
                  <Text style={styles.items} numberOfLines={2}>{o.items.map((i) => `${i.quantity}x ${i.name.fr}${i.size ? ` ${i.size.label}` : ""}`).join(", ")}</Text>
                  <Text style={styles.total}>{chf(o.total)}</Text>
                </Pressable>
              ))}
            </View>
          </View>
        ) : null}
      </ScrollView>
    </View>
  );
}

const useStyles = makeStyles((colors) => ({
  screen: { flex: 1, backgroundColor: colors.surface },
  searchWrap: { flexDirection: "row", alignItems: "center", gap: 10, marginHorizontal: 16, marginTop: 12, height: 52, borderRadius: 14, backgroundColor: colors.surfaceSecondary, borderWidth: 1, borderColor: colors.border, paddingHorizontal: 14 },
  input: { flex: 1, fontFamily: FONT_TEXT, fontSize: 18, fontWeight: "700", color: colors.onSurface, height: 52 },
  hint: { fontFamily: FONT_TEXT, fontSize: 13, color: colors.muted },
  section: { fontFamily: FONT_TEXT, fontSize: 12, fontWeight: "700", color: colors.muted, textTransform: "uppercase", letterSpacing: 0.8, marginBottom: 8 },
  card: { backgroundColor: colors.surfaceSecondary, borderRadius: 16, borderWidth: 1, borderColor: colors.border, padding: 14, gap: 6 },
  rowBetween: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  name: { fontFamily: FONT_TEXT, fontSize: 17, fontWeight: "800", color: colors.onSurface },
  phone: { fontFamily: FONT_TEXT, fontSize: 14, color: colors.onSurfaceSecondary },
  addr: { flexDirection: "row", gap: 6, alignItems: "center" },
  addrText: { fontFamily: FONT_TEXT, fontSize: 13, color: colors.onSurfaceSecondary, flex: 1 },
  num: { fontFamily: FONT_DISPLAY, fontSize: 22, color: colors.onSurface },
  items: { fontFamily: FONT_TEXT, fontSize: 13, color: colors.onSurfaceSecondary },
  total: { fontFamily: FONT_TEXT, fontSize: 15, fontWeight: "800", color: colors.onSurface },
}));
