import React, { useEffect, useState } from "react";
import { ActivityIndicator, KeyboardAvoidingView, Modal, Platform, Pressable, ScrollView, Text, View } from "react-native";
import { useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useQueryClient } from "@tanstack/react-query";
import { Feather } from "@react-native-vector-icons/feather";
import { makeStyles, useTheme } from "@/src/theme";
import { useI18n } from "@/src/i18n";
import { customersApi, useCustomerProfile, useDeleteCustomerAddress, useSaveCustomerAddress, useUpdateCustomer, useUpdateOrderAddress } from "@/src/api";
import { fmtDate, fmtTime } from "@/src/format";
import { Button, Field, FONT_DISPLAY, FONT_TEXT, useToast } from "@/src/components/ui";
import { AddressFields, emptyAddress, fromSaved, type OrderAddress } from "@/src/components/phone/address-fields";
import type { CustomerChangeAudit, CustomerProfile, Order, User } from "@/src/types";

const fill = (s: string, vars: Record<string, string | number>) => Object.entries(vars).reduce((acc, [k, v]) => acc.replace(`{${k}}`, String(v)), s);
/** Delivery orders whose address can still be corrected (the server refuses finished / delivered / cancelled ones). */
const inProgressDelivery = (o: Order) => o.type === "delivery" && !["delivered", "completed", "cancelled"].includes(o.status);

type Identity = { first_name: string; last_name: string; phone: string; email: string };

// ---------------------------------------------------------------------------
// Bottom sheet shell (shared by the editor and the guest -> customer form)
// ---------------------------------------------------------------------------
function Sheet({ visible, onClose, title, testID, children }: { visible: boolean; onClose: () => void; title: string; testID: string; children: React.ReactNode }) {
  const styles = useStyles();
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onClose}>
      <View style={styles.backdrop}>
        <Pressable style={{ flex: 1 }} onPress={onClose} testID={`${testID}-backdrop`} />
        <KeyboardAvoidingView behavior={Platform.OS === "ios" ? "padding" : undefined} style={styles.sheetWrap}>
          <View style={[styles.sheet, { paddingBottom: insets.bottom + 16 }]} testID={testID}>
            <View style={styles.handle} />
            <View style={styles.header}>
              <Text style={styles.title}>{title}</Text>
              <Pressable onPress={onClose} style={styles.iconBtn} testID={`${testID}-close`} hitSlop={8}><Feather name="x" size={20} color={colors.onSurface} /></Pressable>
            </View>
            <ScrollView keyboardShouldPersistTaps="handled" contentContainerStyle={{ gap: 20, paddingBottom: 8 }} showsVerticalScrollIndicator={false}>
              {children}
            </ScrollView>
          </View>
        </KeyboardAvoidingView>
      </View>
    </Modal>
  );
}

function IdentityFields({ f, onChange, prefix, showPhoneHint }: { f: Identity; onChange: (f: Identity) => void; prefix: string; showPhoneHint: boolean }) {
  const styles = useStyles();
  const { t } = useI18n();
  const set = (k: keyof Identity) => (v: string) => onChange({ ...f, [k]: v });
  return (
    <View style={{ gap: 10 }}>
      <View style={styles.two}>
        <Field label={`${t("firstName")} *`} value={f.first_name} onChangeText={set("first_name")} style={{ flex: 1 }} autoCapitalize="words" testID={`${prefix}-first-name`} />
        <Field label={t("lastName")} value={f.last_name} onChangeText={set("last_name")} style={{ flex: 1 }} autoCapitalize="words" testID={`${prefix}-last-name`} />
      </View>
      <Field label={`${t("phone")} *`} value={f.phone} onChangeText={set("phone")} keyboardType="phone-pad" testID={`${prefix}-phone`} />
      {showPhoneHint ? <Text style={styles.warn} testID={`${prefix}-phone-hint`}>{t("phoneChangeHint")}</Text> : null}
      <Field label={t("email")} value={f.email} onChangeText={set("email")} keyboardType="email-address" autoCapitalize="none" autoCorrect={false} testID={`${prefix}-email`} />
    </View>
  );
}

// ---------------------------------------------------------------------------
// Edit an existing customer file (account or phone customer): identity + saved addresses
// ---------------------------------------------------------------------------
interface EditProps {
  customerId: string;
  visible: boolean;
  onClose: () => void;
  /** Fresh user document after every successful change (the phone-order flow keeps its selected customer in sync). */
  onSaved?: (u: User) => void;
}

export function CustomerEditSheet({ customerId, visible, onClose, onSaved }: EditProps) {
  const styles = useStyles();
  const { colors } = useTheme();
  const { t } = useI18n();
  const { data: c, isLoading } = useCustomerProfile(visible ? customerId : undefined);
  return (
    <Sheet visible={visible} onClose={onClose} title={t("editCustomer")} testID="customer-edit-sheet">
      {isLoading || !c ? (
        <View style={{ paddingVertical: 32 }}><ActivityIndicator color={colors.brandPrimary} /></View>
      ) : (
        <>
          <IdentitySection c={c} onSaved={(u) => onSaved?.(u)} />
          <AddressesSection c={c} onSaved={(u) => onSaved?.(u)} />
          <Text style={styles.hint} testID="customer-edit-past-orders-hint">{t("pastOrdersUnchanged")}</Text>
          <ChangesJournal entries={c.changes_audit ?? []} />
        </>
      )}
    </Sheet>
  );
}

function IdentitySection({ c, onSaved }: { c: CustomerProfile; onSaved: (u: User) => void }) {
  const styles = useStyles();
  const { t } = useI18n();
  const toast = useToast();
  const update = useUpdateCustomer();
  const initial = (): Identity => ({ first_name: c.first_name, last_name: c.last_name, phone: c.phone, email: c.email ?? "" });
  const [f, setF] = useState<Identity>(initial);
  useEffect(() => { setF(initial()); }, [c.key]); // eslint-disable-line react-hooks/exhaustive-deps
  const digits = f.phone.replace(/\D/g, "");
  const dirty = f.first_name !== c.first_name || f.last_name !== c.last_name || f.phone !== c.phone || f.email !== (c.email ?? "");
  const phoneChanged = digits !== c.phone.replace(/\D/g, "");

  const save = async () => {
    if (!f.first_name.trim() || digits.length < 7) {
      toast.show(t("required"), "error");
      return;
    }
    try {
      const u = await update.mutateAsync({ id: c.key, first_name: f.first_name.trim(), last_name: f.last_name.trim(), phone: f.phone.trim(), email: f.email.trim() || null });
      toast.show(t("customerUpdated"), "success");
      onSaved(u);
    } catch (e: any) {
      toast.show(e?.message || "Erreur", "error");
    }
  };

  return (
    <View style={{ gap: 10 }} testID="customer-edit-identity">
      <Text style={styles.section}>{t("customerIdentity")}</Text>
      <IdentityFields f={f} onChange={setF} prefix="customer-edit" showPhoneHint={phoneChanged} />
      <Button title={t("save")} icon="check" onPress={save} disabled={!dirty} loading={update.isPending} testID="customer-edit-save" />
    </View>
  );
}

function AddressesSection({ c, onSaved }: { c: CustomerProfile; onSaved: (u: User) => void }) {
  const styles = useStyles();
  const { colors } = useTheme();
  const { t } = useI18n();
  const toast = useToast();
  const save = useSaveCustomerAddress();
  const del = useDeleteCustomerAddress();
  const applyOrder = useUpdateOrderAddress();
  const addrs = c.saved_addresses ?? [];
  const active = c.orders.filter(inProgressDelivery);
  const [editing, setEditing] = useState<{ id: string | null; label: string; a: OrderAddress } | null>(null);
  const [confirmDel, setConfirmDel] = useState(false);
  const valid = !!editing && !!editing.a.street.trim() && !!editing.a.npa.trim() && !!editing.a.city.trim();
  const body = () => ({ street: editing!.a.street.trim(), number: editing!.a.number.trim(), npa: editing!.a.npa.trim(), city: editing!.a.city.trim(), instructions: editing!.a.instructions.trim() || null });

  const submit = async () => {
    if (!valid) {
      toast.show(t("required"), "error");
      return;
    }
    try {
      const u = await save.mutateAsync({ id: c.key, addrId: editing!.id, label: editing!.label, ...body() });
      toast.show(t("saved"), "success");
      onSaved(u);
      setEditing(null);
    } catch (e: any) {
      toast.show(e?.message || "Erreur", "error");
    }
  };
  const remove = async () => {
    try {
      const u = await del.mutateAsync({ id: c.key, addrId: editing!.id! });
      toast.show(t("addressDeleted"), "success");
      onSaved(u);
      setEditing(null);
      setConfirmDel(false);
    } catch (e: any) {
      toast.show(e?.message || "Erreur", "error");
    }
  };
  const apply = async (o: Order) => {
    if (!valid) {
      toast.show(t("required"), "error");
      return;
    }
    try {
      await applyOrder.mutateAsync({ id: o.id, ...body() });
      toast.show(fill(t("addressAppliedToOrder"), { n: o.order_number }), "success");
    } catch (e: any) {
      toast.show(e?.message || "Erreur", "error");
    }
  };

  return (
    <View style={{ gap: 10 }} testID="customer-edit-addresses">
      <Text style={styles.section}>{t("savedAddresses")} ({addrs.length})</Text>
      {addrs.length === 0 && !editing ? <Text style={styles.hint}>{t("noAddresses")}</Text> : null}
      {addrs.map((a) => (
        <Pressable key={a.id} onPress={() => { setEditing({ id: a.id, label: a.label, a: fromSaved(a) }); setConfirmDel(false); }} style={[styles.addrRow, editing?.id === a.id && styles.addrRowActive]} testID={`customer-edit-addr-${a.id}`}>
          <Feather name="map-pin" size={14} color={colors.brandPrimary} />
          <Text style={styles.addrText}>{a.label ? `${a.label} · ` : ""}{a.street} {a.number}, {a.npa} {a.city}{a.instructions ? `\n${a.instructions}` : ""}</Text>
          <Feather name="edit-2" size={16} color={colors.muted} />
        </Pressable>
      ))}
      {!editing ? (
        <Button title={t("addAddress")} variant="outline" icon="plus" onPress={() => { setEditing({ id: null, label: "", a: emptyAddress() }); setConfirmDel(false); }} testID="customer-edit-addr-add" />
      ) : (
        <View style={styles.editor} testID="customer-edit-addr-form">
          <Text style={styles.editorTitle}>{editing.id ? t("editAddress") : t("addAddress")}</Text>
          <AddressFields a={editing.a} onChange={(a) => setEditing({ ...editing, a })} prefix="customer-edit-addr" />
          <View style={styles.two}>
            <Button title={t("close")} variant="secondary" onPress={() => setEditing(null)} style={{ flex: 1 }} testID="customer-edit-addr-cancel" />
            <Button title={t("save")} icon="check" onPress={submit} loading={save.isPending} style={{ flex: 1 }} testID="customer-edit-addr-save" />
          </View>
          {editing.id ? (
            confirmDel
              ? <Button title={t("confirmDelete")} variant="danger" icon="trash-2" onPress={remove} loading={del.isPending} testID="customer-edit-addr-delete-confirm" />
              : <Button title={t("deleteAddress")} variant="outline" icon="trash-2" onPress={() => setConfirmDel(true)} testID="customer-edit-addr-delete" />
          ) : null}
          {active.length ? (
            <View style={{ gap: 8 }} testID="customer-edit-apply-orders">
              <Text style={styles.editorTitle}>{t("inProgressOrders")}</Text>
              {active.map((o) => (
                <Button key={o.id} title={fill(t("applyToOrder"), { n: o.order_number })} variant="success" icon="truck" onPress={() => apply(o)} disabled={!valid} loading={applyOrder.isPending} testID={`customer-edit-apply-${o.id}`} />
              ))}
            </View>
          ) : null}
        </View>
      )}
    </View>
  );
}

/** Journal of staff corrections (who changed what, when) – shown in the editor and on the customer profile. */
export function ChangesJournal({ entries }: { entries: CustomerChangeAudit[] }) {
  const styles = useStyles();
  const { t } = useI18n();
  if (!entries.length) return null;
  const label = (f: string) => (f === "first_name" ? t("firstName") : f === "last_name" ? t("lastName") : f === "phone" ? t("phone") : f === "email" ? t("email") : t("deliveryAddress"));
  return (
    <View style={{ gap: 4 }} testID="customer-changes-audit">
      <Text style={styles.section}>{t("customerChangesTitle")}</Text>
      {entries.map((e) => (
        <Text key={e.id} style={styles.auditLine} testID={`customer-change-${e.id}`}>
          {e.at ? `${fmtDate(e.at)} ${fmtTime(e.at)}` : "–"} · {e.changes.map((ch) => `${label(ch.field)}: ${ch.previous || "—"} → ${ch.new || "—"}`).join(" · ")} · {e.manager || "staff"}
        </Text>
      ))}
    </View>
  );
}

// ---------------------------------------------------------------------------
// Guest (orders only, no document) -> real customer file, prefilled from the latest order
// ---------------------------------------------------------------------------
export function GuestToCustomerSheet({ c, visible, onClose }: { c: CustomerProfile; visible: boolean; onClose: () => void }) {
  const styles = useStyles();
  const { t } = useI18n();
  const toast = useToast();
  const router = useRouter();
  const qc = useQueryClient();
  const last = c.orders.find((o) => o.address)?.address;
  const [f, setF] = useState<Identity>({ first_name: c.first_name, last_name: c.last_name, phone: c.phone, email: c.email ?? "" });
  const [a, setA] = useState<OrderAddress>(last ? { street: last.street, number: last.number, npa: last.npa, city: last.city, instructions: last.instructions || "" } : emptyAddress());
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    const digits = f.phone.replace(/\D/g, "");
    if (!f.first_name.trim() || digits.length < 7) {
      toast.show(t("required"), "error");
      return;
    }
    setBusy(true);
    try {
      const hasAddr = a.street.trim() && a.npa.trim() && a.city.trim();
      const u = await customersApi.create({
        first_name: f.first_name.trim(), last_name: f.last_name.trim(), phone: digits, email: f.email.trim() || undefined,
        address: hasAddr ? { label: "", street: a.street.trim(), number: a.number.trim(), npa: a.npa.trim(), city: a.city.trim(), instructions: a.instructions.trim() || null } : null,
      });
      qc.invalidateQueries({ queryKey: ["customers"] });
      toast.show(t("saved"), "success");
      onClose();
      router.replace({ pathname: "/staff/customers/[key]", params: { key: u.id } });
    } catch (e: any) {
      toast.show(e?.message || "Erreur", "error");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Sheet visible={visible} onClose={onClose} title={t("createCustomerFile")} testID="guest-create-sheet">
      <Text style={styles.hint}>{t("createCustomerFileHint")}</Text>
      <View style={{ gap: 10 }}>
        <Text style={styles.section}>{t("customerIdentity")}</Text>
        <IdentityFields f={f} onChange={setF} prefix="guest-create" showPhoneHint={false} />
      </View>
      <View style={{ gap: 10 }}>
        <Text style={styles.section}>{t("deliveryAddress")}</Text>
        <AddressFields a={a} onChange={setA} prefix="guest-create-addr" />
      </View>
      <Button title={t("saveCustomer")} size="lg" icon="user-plus" onPress={submit} loading={busy} testID="guest-create-save" />
    </Sheet>
  );
}

const useStyles = makeStyles((colors) => ({
  backdrop: { flex: 1, backgroundColor: colors.scrim, justifyContent: "flex-end" },
  sheetWrap: { width: "100%", maxWidth: 720, alignSelf: "center" },
  sheet: { backgroundColor: colors.surface, borderTopLeftRadius: 24, borderTopRightRadius: 24, paddingHorizontal: 20, paddingTop: 10, maxHeight: "92%" },
  handle: { alignSelf: "center", width: 40, height: 4, borderRadius: 2, backgroundColor: colors.borderStrong, marginBottom: 10 },
  header: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: 12, marginBottom: 14 },
  title: { fontFamily: FONT_DISPLAY, fontSize: 22, color: colors.onSurface, flex: 1 },
  iconBtn: { width: 44, height: 44, borderRadius: 22, backgroundColor: colors.surfaceSecondary, borderWidth: 1, borderColor: colors.border, alignItems: "center", justifyContent: "center" },
  section: { fontFamily: FONT_TEXT, fontSize: 12, fontWeight: "700", color: colors.muted, textTransform: "uppercase", letterSpacing: 0.8 },
  two: { flexDirection: "row", gap: 10 },
  hint: { fontFamily: FONT_TEXT, fontSize: 13, lineHeight: 18, color: colors.muted },
  warn: { fontFamily: FONT_TEXT, fontSize: 13, lineHeight: 18, color: colors.brandPrimary, fontWeight: "600" },
  addrRow: { flexDirection: "row", alignItems: "center", gap: 10, padding: 12, borderRadius: 12, borderWidth: 1, borderColor: colors.border, backgroundColor: colors.surfaceSecondary, minHeight: 48 },
  addrRowActive: { borderColor: colors.brandPrimary, borderWidth: 1.5 },
  addrText: { flex: 1, fontFamily: FONT_TEXT, fontSize: 14, lineHeight: 19, color: colors.onSurface },
  editor: { gap: 12, padding: 14, borderRadius: 16, borderWidth: 1, borderColor: colors.border, backgroundColor: colors.surfaceSecondary },
  editorTitle: { fontFamily: FONT_TEXT, fontSize: 14, fontWeight: "800", color: colors.onSurface },
  auditLine: { fontFamily: FONT_TEXT, fontSize: 12, lineHeight: 17, color: colors.onSurfaceSecondary },
}));
