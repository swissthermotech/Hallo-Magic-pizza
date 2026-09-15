import React, { useMemo, useState } from "react";
import { ActivityIndicator, Pressable, Text, TextInput, View } from "react-native";
import { Feather } from "@react-native-vector-icons/feather";
import { useQueryClient } from "@tanstack/react-query";
import { makeStyles, useTheme } from "@/src/theme";
import { useI18n } from "@/src/i18n";
import { customersApi, useCustomerSearch } from "@/src/api";
import { Button, Chip, Field, FONT_DISPLAY, FONT_TEXT, useToast } from "@/src/components/ui";
import type { Order, SavedAddress, User } from "@/src/types";

export type OrderAddress = { street: string; number: string; npa: string; city: string; instructions: string };
export const emptyAddress = (): OrderAddress => ({ street: "", number: "", npa: "", city: "", instructions: "" });
const fromSaved = (a: SavedAddress): OrderAddress => ({ street: a.street, number: a.number, npa: a.npa, city: a.city, instructions: a.instructions || "" });

interface Props {
  customer: User | null;
  onCustomer: (u: User | null) => void;
  address: OrderAddress;
  onAddress: (a: OrderAddress) => void;
  savedAddrId: string | null;
  onSavedAddr: (id: string | null) => void;
  saveAddress: boolean;
  onSaveAddress: (v: boolean) => void;
  delivery: boolean;
}

/** Step 1 of a phone order: find the caller by phone number, or create the customer quickly. */
export function CustomerPanel(p: Props) {
  const styles = useStyles();
  const { colors } = useTheme();
  const { t } = useI18n();
  const toast = useToast();
  const qc = useQueryClient();
  const [phone, setPhone] = useState("");
  const { data, isFetching } = useCustomerSearch(phone);
  const digits = phone.replace(/\D/g, "");
  const [nf, setNf] = useState({ first_name: "", last_name: "", street: "", number: "", npa: "", city: "", instructions: "" });
  const [busy, setBusy] = useState(false);
  const setN = (k: keyof typeof nf) => (v: string) => setNf((x) => ({ ...x, [k]: v }));
  const [editAddr, setEditAddr] = useState(false);

  // Guest orders matching the number -> offer their details as a "new customer" prefill
  const guestHint = useMemo(() => {
    const o: Order | undefined = data?.orders.find((x) => !x.user_id);
    return o ?? null;
  }, [data]);

  const select = (u: User) => {
    p.onCustomer(u);
    setPhone("");
    if (u.addresses.length) {
      p.onSavedAddr(u.addresses[0].id);
      p.onAddress(fromSaved(u.addresses[0]));
    } else {
      p.onSavedAddr(null);
      p.onAddress(emptyAddress());
    }
    setEditAddr(false);
  };

  const createCustomer = async () => {
    if (!nf.first_name.trim() || digits.length < 7) {
      toast.show(t("required"), "error");
      return;
    }
    setBusy(true);
    try {
      const hasAddr = nf.street.trim() && nf.npa.trim() && nf.city.trim();
      const u = await customersApi.create({
        first_name: nf.first_name.trim(), last_name: nf.last_name.trim(), phone: digits,
        address: hasAddr ? { label: "", street: nf.street.trim(), number: nf.number.trim(), npa: nf.npa.trim(), city: nf.city.trim(), instructions: nf.instructions.trim() || null } : null,
      });
      qc.invalidateQueries({ queryKey: ["customers"] });
      select(u);
      setPhone("");
      toast.show(t("saved"), "success");
    } catch (e: any) {
      toast.show(e?.message || "Erreur", "error");
    } finally {
      setBusy(false);
    }
  };

  const useGuest = (o: Order) => {
    setNf({ first_name: o.customer.first_name, last_name: o.customer.last_name, street: o.address?.street ?? "", number: o.address?.number ?? "", npa: o.address?.npa ?? "", city: o.address?.city ?? "", instructions: o.address?.instructions ?? "" });
  };

  // ---- Selected customer ----
  if (p.customer) {
    const u = p.customer;
    return (
      <View style={styles.card} testID="phone-customer-card">
        <View style={styles.rowBetween}>
          <View style={{ flex: 1 }}>
            <Text style={styles.kicker}>{t("existingCustomer")}</Text>
            <Text style={styles.name} testID="phone-customer-name">{u.first_name} {u.last_name}</Text>
            <Text style={styles.info}>{u.phone}{u.email ? ` · ${u.email}` : ""}</Text>
          </View>
          <Button title={t("changeCustomer")} variant="outline" icon="x" onPress={() => { p.onCustomer(null); p.onAddress(emptyAddress()); p.onSavedAddr(null); }} testID="phone-change-customer" />
        </View>
        {p.delivery ? (
          <View style={{ gap: 10, marginTop: 12 }}>
            <Text style={styles.kicker}>{t("deliveryAddress")}</Text>
            {u.addresses.length ? (
              <View style={styles.wrap}>
                {u.addresses.map((a) => (
                  <Chip key={a.id} label={`${a.label ? a.label + " · " : ""}${a.street} ${a.number}, ${a.npa} ${a.city}`.trim()} selected={p.savedAddrId === a.id} onPress={() => { p.onSavedAddr(a.id); p.onAddress(fromSaved(a)); setEditAddr(false); }} testID={`phone-addr-${a.id}`} />
                ))}
                <Chip label={t("newAddress")} selected={!p.savedAddrId} onPress={() => { p.onSavedAddr(null); p.onAddress(emptyAddress()); setEditAddr(true); }} testID="phone-addr-new" />
              </View>
            ) : null}
            {!editAddr && p.savedAddrId ? (
              <View style={styles.rowBetween}>
                <Text style={[styles.info, { flex: 1 }]} testID="phone-addr-text">{p.address.street} {p.address.number}, {p.address.npa} {p.address.city}{p.address.instructions ? `\n${p.address.instructions}` : ""}</Text>
                <Pressable testID="phone-addr-edit" onPress={() => setEditAddr(true)} style={styles.link}><Feather name="edit-2" size={14} color={colors.brandPrimary} /><Text style={styles.linkText}>{t("editForThisOrder")}</Text></Pressable>
              </View>
            ) : (
              <AddressFields a={p.address} onChange={p.onAddress} prefix="phone-order" />
            )}
            {!p.savedAddrId || editAddr ? (
              <Pressable testID="phone-save-address" onPress={() => p.onSaveAddress(!p.saveAddress)} style={styles.checkRow}>
                <View style={[styles.checkbox, p.saveAddress && styles.checkboxOn]}>{p.saveAddress ? <Feather name="check" size={14} color={colors.onBrandPrimary} /> : null}</View>
                <Text style={styles.info}>{t("saveToCustomer")}</Text>
              </Pressable>
            ) : null}
          </View>
        ) : null}
      </View>
    );
  }

  // ---- Search / create ----
  return (
    <View style={{ gap: 12 }}>
      <View style={styles.searchWrap}>
        <Feather name="phone" size={22} color={colors.brandPrimary} />
        <TextInput
          testID="phone-search-input"
          value={phone}
          onChangeText={setPhone}
          placeholder={t("callerPhone")}
          placeholderTextColor={colors.muted}
          keyboardType="phone-pad"
          autoFocus
          style={styles.searchInput}
        />
        {isFetching ? <ActivityIndicator color={colors.brandPrimary} /> : null}
      </View>

      {data && data.accounts.length > 0 ? (
        <View style={{ gap: 8 }}>
          <Text style={styles.kicker}>{t("existingCustomer")} ({data.accounts.length})</Text>
          {data.accounts.map((u) => (
            <Pressable key={u.id} testID={`phone-result-${u.id}`} onPress={() => select(u)} style={({ pressed }) => [styles.result, pressed && { opacity: 0.85 }]}>
              <View style={styles.avatar}><Text style={styles.avatarText}>{u.first_name.charAt(0).toUpperCase()}</Text></View>
              <View style={{ flex: 1 }}>
                <Text style={styles.name}>{u.first_name} {u.last_name}</Text>
                <Text style={styles.info}>{u.phone}{u.addresses[0] ? ` · ${u.addresses[0].street} ${u.addresses[0].number}, ${u.addresses[0].npa} ${u.addresses[0].city}` : ""}</Text>
              </View>
              <Feather name="chevron-right" size={22} color={colors.muted} />
            </Pressable>
          ))}
        </View>
      ) : null}

      {digits.length >= 7 && data && data.accounts.length === 0 ? (
        <View style={styles.card} testID="phone-new-customer">
          <Text style={styles.kicker}>{t("newCustomer")} · {digits}</Text>
          {guestHint ? (
            <Pressable testID="phone-use-guest" onPress={() => useGuest(guestHint)} style={styles.guestRow}>
              <Feather name="clock" size={16} color={colors.brandPrimary} />
              <Text style={[styles.info, { flex: 1 }]}>{t("customerFromOrders")}: {guestHint.customer.first_name} {guestHint.customer.last_name}{guestHint.address ? `, ${guestHint.address.street} ${guestHint.address.number}` : ""}</Text>
              <Text style={styles.linkText}>{t("useTheseDetails")}</Text>
            </Pressable>
          ) : null}
          <View style={styles.two}>
            <Field label={`${t("firstName")} *`} value={nf.first_name} onChangeText={setN("first_name")} style={{ flex: 1 }} autoCapitalize="words" testID="phone-new-first-name" />
            <Field label={t("lastName")} value={nf.last_name} onChangeText={setN("last_name")} style={{ flex: 1 }} autoCapitalize="words" testID="phone-new-last-name" />
          </View>
          <AddressFields a={{ street: nf.street, number: nf.number, npa: nf.npa, city: nf.city, instructions: nf.instructions }} onChange={(a) => setNf((x) => ({ ...x, ...a }))} prefix="phone-new" />
          <Button title={t("saveCustomer")} size="lg" icon="user-plus" loading={busy} onPress={createCustomer} testID="phone-new-save" />
        </View>
      ) : digits.length < 3 ? <Text style={styles.hint}>{t("searchHint")}</Text> : null}
    </View>
  );
}

export function AddressFields({ a, onChange, prefix }: { a: OrderAddress; onChange: (a: OrderAddress) => void; prefix: string }) {
  const styles = useStyles();
  const { t } = useI18n();
  const set = (k: keyof OrderAddress) => (v: string) => onChange({ ...a, [k]: v });
  return (
    <View style={{ gap: 10 }}>
      <View style={styles.two}>
        <Field label={`${t("street")} *`} value={a.street} onChangeText={set("street")} style={{ flex: 3 }} testID={`${prefix}-street`} />
        <Field label={t("number")} value={a.number} onChangeText={set("number")} style={{ flex: 1 }} testID={`${prefix}-number`} />
      </View>
      <View style={styles.two}>
        <Field label={`${t("npa")} *`} value={a.npa} onChangeText={set("npa")} keyboardType="number-pad" style={{ flex: 1 }} testID={`${prefix}-npa`} />
        <Field label={`${t("city")} *`} value={a.city} onChangeText={set("city")} style={{ flex: 2 }} testID={`${prefix}-city`} />
      </View>
      <Field label={t("deliveryInstructions")} value={a.instructions} onChangeText={set("instructions")} testID={`${prefix}-instructions`} />
    </View>
  );
}

const useStyles = makeStyles((colors) => ({
  searchWrap: { flexDirection: "row", alignItems: "center", gap: 12, height: 64, borderRadius: 18, backgroundColor: colors.surfaceSecondary, borderWidth: 2, borderColor: colors.brandPrimary, paddingHorizontal: 18 },
  searchInput: { flex: 1, fontFamily: FONT_TEXT, fontSize: 24, fontWeight: "800", color: colors.onSurface, height: 64, letterSpacing: 1 },
  hint: { fontFamily: FONT_TEXT, fontSize: 13, color: colors.muted },
  kicker: { fontFamily: FONT_TEXT, fontSize: 11, fontWeight: "800", color: colors.muted, textTransform: "uppercase", letterSpacing: 0.8 },
  card: { backgroundColor: colors.surfaceSecondary, borderRadius: 18, borderWidth: 1, borderColor: colors.border, padding: 16, gap: 10 },
  result: { flexDirection: "row", alignItems: "center", gap: 12, backgroundColor: colors.surfaceSecondary, borderRadius: 16, borderWidth: 1.5, borderColor: colors.border, padding: 14, minHeight: 64 },
  avatar: { width: 40, height: 40, borderRadius: 20, backgroundColor: colors.brandSoft, alignItems: "center", justifyContent: "center" },
  avatarText: { fontFamily: FONT_DISPLAY, fontSize: 20, color: colors.brandPrimary },
  name: { fontFamily: FONT_TEXT, fontSize: 18, fontWeight: "800", color: colors.onSurface },
  info: { fontFamily: FONT_TEXT, fontSize: 14, color: colors.onSurfaceSecondary, lineHeight: 20 },
  rowBetween: { flexDirection: "row", alignItems: "center", gap: 10 },
  wrap: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  two: { flexDirection: "row", gap: 10 },
  link: { flexDirection: "row", alignItems: "center", gap: 6, paddingVertical: 8 },
  linkText: { fontFamily: FONT_TEXT, fontSize: 13, fontWeight: "700", color: colors.brandPrimary },
  checkRow: { flexDirection: "row", alignItems: "center", gap: 10, paddingVertical: 4 },
  checkbox: { width: 24, height: 24, borderRadius: 6, borderWidth: 2, borderColor: colors.borderStrong, alignItems: "center", justifyContent: "center" },
  checkboxOn: { backgroundColor: colors.brandPrimary, borderColor: colors.brandPrimary },
  guestRow: { flexDirection: "row", alignItems: "center", gap: 8, backgroundColor: colors.brandSoft, borderRadius: 12, padding: 12 },
}));
