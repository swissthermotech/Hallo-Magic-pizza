import React, { useEffect, useState } from "react";
import { ActivityIndicator, Modal, Pressable, ScrollView, Text, useWindowDimensions, View } from "react-native";
import { Redirect, useRouter } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { KeyboardAwareScrollView } from "react-native-keyboard-controller";
import { Feather } from "@react-native-vector-icons/feather";
import * as Haptics from "expo-haptics";
import { makeStyles, useTheme } from "@/src/theme";
import { useI18n } from "@/src/i18n";
import { useMenu, usePlacePhoneOrder } from "@/src/api";
import { useCart } from "@/src/cart";
import { useStaff } from "@/src/staff-auth";
import { storage } from "@/src/utils/storage";
import { chf } from "@/src/format";
import { Button, FONT_DISPLAY, FONT_TEXT, useToast } from "@/src/components/ui";
import { CustomerPanel, emptyAddress, type OrderAddress } from "@/src/components/phone/customer-panel";
import { MenuPanel } from "@/src/components/phone/menu-panel";
import { OrderPanel, type PaymentMethod } from "@/src/components/phone/order-panel";
import type { Order, User } from "@/src/types";

const STATION_KEY = "phone_station";

/**
 * /phone-orders – restaurant iPads (Poste 1 / Poste 2) taking orders by telephone.
 * Same backend, customers, menu, VAT, ticket and dashboard as the customer app.
 */
export default function PhoneOrdersScreen() {
  const styles = useStyles();
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const { t, lang } = useI18n();
  const toast = useToast();
  const { ready, unlocked, role } = useStaff();
  const { width } = useWindowDimensions();
  const wide = width >= 900;
  const { data } = useMenu();
  const cart = useCart();
  const place = usePlacePhoneOrder();

  const [station, setStation] = useState<number | null>(null);
  const [stationReady, setStationReady] = useState(false);
  const [pickStation, setPickStation] = useState(false);
  useEffect(() => {
    storage.getItem<number>(STATION_KEY, 0).then((v) => {
      setStation(v || null);
      setStationReady(true);
    });
  }, []);
  const chooseStation = (n: number) => {
    setStation(n);
    setPickStation(false);
    storage.setItem(STATION_KEY, n);
  };

  const [customer, setCustomer] = useState<User | null>(null);
  const [address, setAddress] = useState<OrderAddress>(emptyAddress());
  const [savedAddrId, setSavedAddrId] = useState<string | null>(null);
  const [saveAddress, setSaveAddress] = useState(true);
  const [timeMode, setTimeMode] = useState<"asap" | "exact">("asap");
  const [time, setTime] = useState("");
  const [payment, setPayment] = useState<PaymentMethod>("cash");
  const [pane, setPane] = useState<"entry" | "order">("entry");
  const [done, setDone] = useState<Order | null>(null);
  const [requestId, setRequestId] = useState(() => `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`);

  const reset = () => {
    cart.clear();
    setCustomer(null);
    setAddress(emptyAddress());
    setSavedAddrId(null);
    setTimeMode("asap");
    setTime("");
    setPayment("cash");
    setDone(null);
    setPane("entry");
    setRequestId(`${Date.now()}-${Math.random().toString(36).slice(2, 8)}`);
  };

  const confirm = async () => {
    if (!customer || !station || place.isPending) return;
    const delivery = cart.orderType === "delivery";
    try {
      const order = await place.mutateAsync({
        type: cart.orderType,
        station,
        payment_method: payment,
        customer_id: customer.id,
        client_request_id: `${station}-${requestId}`,
        items: cart.items,
        customer: { first_name: customer.first_name, last_name: customer.last_name, phone: customer.phone, email: customer.email || undefined },
        address: delivery ? { street: address.street.trim(), number: address.number.trim(), npa: address.npa.trim(), city: address.city.trim(), instructions: address.instructions.trim() || undefined } : undefined,
        requested_time: timeMode === "asap" ? "asap" : time.trim(),
        general_note: cart.generalNote.trim() || undefined,
        age_confirmed: true,
        save_address: delivery && !savedAddrId && saveAddress,
        language: lang,
      });
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success).catch(() => {});
      cart.clear();
      setDone(order);
    } catch (e: any) {
      toast.show(e?.message || "Erreur", "error");
    }
  };

  if (!ready || !stationReady) return <View style={[styles.screen, styles.center]}><ActivityIndicator color={colors.brandPrimary} /></View>;
  if (!unlocked) return <Redirect href="/staff/login" />;
  if (role && !["manager", "phone"].includes(role)) return <Redirect href={role.startsWith("driver") ? "/driver" : "/staff"} />;

  const entry = (
    <View style={{ gap: 18 }}>
      <Text style={styles.step}>1 · {t("callerPhone")}</Text>
      <CustomerPanel customer={customer} onCustomer={setCustomer} address={address} onAddress={setAddress} savedAddrId={savedAddrId} onSavedAddr={setSavedAddrId} saveAddress={saveAddress} onSaveAddress={setSaveAddress} delivery={cart.orderType === "delivery"} />
      <Text style={styles.step}>2 · {t("menu")}</Text>
      <MenuPanel />
    </View>
  );
  const order = <OrderPanel settings={data?.settings} customer={customer} address={address} timeMode={timeMode} onTimeMode={setTimeMode} time={time} onTime={setTime} payment={payment} onPayment={setPayment} onConfirm={confirm} busy={place.isPending} station={station ?? 1} />;

  return (
    <View style={styles.screen}>
      {/* Header */}
      <View style={[styles.header, { paddingTop: insets.top + 8 }]}>
        <Pressable testID="phone-back" onPress={() => (router.canGoBack() ? router.back() : router.replace("/staff"))} style={styles.iconBtn}><Feather name="arrow-left" size={20} color={colors.onSurface} /></Pressable>
        <View style={{ flex: 1 }}>
          <Text style={styles.title} testID="phone-orders-title">{t("phoneOrders")}</Text>
          <Text style={styles.subtitle}>Hallo Magic Pizza · iPad</Text>
        </View>
        <Pressable testID="phone-station-badge" onPress={() => setPickStation(true)} style={styles.stationBadge}>
          <Feather name="phone" size={14} color={colors.onWarning} />
          <Text style={styles.stationText}>{t("phoneStation")} {station ?? "?"}</Text>
        </Pressable>
        <Pressable testID="phone-go-dashboard" onPress={() => router.push("/staff")} style={styles.iconBtn}><Feather name="grid" size={20} color={colors.onSurface} /></Pressable>
      </View>

      {!wide ? (
        <View style={styles.paneSwitch}>
          <Pressable testID="phone-pane-entry" onPress={() => setPane("entry")} style={[styles.paneBtn, pane === "entry" && styles.paneBtnOn]}><Text style={[styles.paneText, pane === "entry" && styles.paneTextOn]}>{t("customers")} & {t("menu")}</Text></Pressable>
          <Pressable testID="phone-pane-order" onPress={() => setPane("order")} style={[styles.paneBtn, pane === "order" && styles.paneBtnOn]}><Text style={[styles.paneText, pane === "order" && styles.paneTextOn]}>{t("cart")} ({cart.count}) · {chf(cart.subtotal + cart.extrasTotal)}</Text></Pressable>
        </View>
      ) : null}

      {wide ? (
        <View style={{ flex: 1, flexDirection: "row" }}>
          <KeyboardAwareScrollView style={{ flex: 1, minWidth: 0 }} contentContainerStyle={{ padding: 16, paddingBottom: insets.bottom + 40 }} bottomOffset={40} keyboardShouldPersistTaps="handled">{entry}</KeyboardAwareScrollView>
          <ScrollView style={styles.rightPane} contentContainerStyle={{ padding: 16, paddingBottom: insets.bottom + 40 }} keyboardShouldPersistTaps="handled">{order}</ScrollView>
        </View>
      ) : (
        <KeyboardAwareScrollView contentContainerStyle={{ padding: 16, paddingBottom: insets.bottom + 40 }} bottomOffset={40} keyboardShouldPersistTaps="handled">{pane === "entry" ? entry : order}</KeyboardAwareScrollView>
      )}

      {/* Station picker (first use / change) */}
      <Modal visible={(station === null || pickStation) && !done} transparent animationType="fade" onRequestClose={() => station && setPickStation(false)}>
        <View style={styles.overlay}>
          <View style={styles.sheet} testID="phone-station-picker">
            <Text style={styles.sheetTitle}>{t("choosePost")}</Text>
            <Text style={styles.hint}>{t("choosePostHint")}</Text>
            <View style={{ flexDirection: "row", gap: 12, marginTop: 8 }}>
              {[1, 2].map((n) => (
                <Pressable key={n} testID={`phone-station-${n}`} onPress={() => chooseStation(n)} style={[styles.stationBtn, station === n && styles.stationBtnOn]}>
                  <Feather name="tablet" size={28} color={colors.onSurfaceInverse} />
                  <Text style={styles.stationBtnText}>{t("post")} {n}</Text>
                </Pressable>
              ))}
            </View>
          </View>
        </View>
      </Modal>

      {/* Success */}
      <Modal visible={!!done} transparent animationType="fade">
        <View style={styles.overlay}>
          <View style={styles.sheet} testID="phone-success">
            <View style={styles.successIcon}><Feather name="check" size={36} color={colors.onSuccess} /></View>
            <Text style={styles.sheetTitle}>{t("phoneOrderCreated")}</Text>
            <Text style={styles.orderNum} testID="phone-success-number">#{done?.order_number}</Text>
            <Text style={styles.hint}>{t("phoneStation")} {done?.station} · {done?.type === "pickup" ? t("pickup") : t("delivery")} · {chf(done?.total ?? 0)}</Text>
            <Text style={styles.hint}>{t("phoneOrderCreatedHint")}</Text>
            <View style={{ flexDirection: "row", gap: 10, marginTop: 8 }}>
              <Button title={t("ticketPreview")} variant="outline" icon="file-text" onPress={() => { const id = done!.id; reset(); router.push({ pathname: "/staff/ticket/[id]", params: { id } }); }} style={{ flex: 1 }} testID="phone-success-ticket" />
              <Button title={t("newPhoneOrder")} icon="plus" onPress={reset} style={{ flex: 1 }} testID="phone-success-new" />
            </View>
          </View>
        </View>
      </Modal>
    </View>
  );
}

const useStyles = makeStyles((colors) => ({
  screen: { flex: 1, backgroundColor: colors.surface },
  center: { alignItems: "center", justifyContent: "center" },
  header: { flexDirection: "row", alignItems: "center", gap: 10, paddingHorizontal: 12, paddingBottom: 10, borderBottomWidth: 1, borderBottomColor: colors.border, backgroundColor: colors.surface },
  title: { fontFamily: FONT_DISPLAY, fontSize: 22, color: colors.onSurface },
  subtitle: { fontFamily: FONT_TEXT, fontSize: 12, color: colors.muted },
  iconBtn: { width: 44, height: 44, borderRadius: 22, backgroundColor: colors.surfaceSecondary, borderWidth: 1, borderColor: colors.border, alignItems: "center", justifyContent: "center" },
  stationBadge: { flexDirection: "row", alignItems: "center", gap: 8, height: 40, paddingHorizontal: 14, borderRadius: 999, backgroundColor: colors.warning },
  stationText: { fontFamily: FONT_TEXT, fontSize: 13, fontWeight: "900", color: colors.onWarning, letterSpacing: 0.6 },
  paneSwitch: { flexDirection: "row", gap: 6, padding: 10, backgroundColor: colors.surfaceTertiary },
  paneBtn: { flex: 1, height: 44, borderRadius: 12, alignItems: "center", justifyContent: "center" },
  paneBtnOn: { backgroundColor: colors.surfaceInverse },
  paneText: { fontFamily: FONT_TEXT, fontSize: 13, fontWeight: "800", color: colors.onSurface },
  paneTextOn: { color: colors.onSurfaceInverse },
  rightPane: { width: 400, flexGrow: 0, flexShrink: 0, borderLeftWidth: 1, borderLeftColor: colors.border, backgroundColor: colors.surface },
  step: { fontFamily: FONT_DISPLAY, fontSize: 22, color: colors.onSurface },
  overlay: { flex: 1, backgroundColor: colors.overlay, alignItems: "center", justifyContent: "center", padding: 24 },
  sheet: { width: "100%", maxWidth: 480, backgroundColor: colors.surface, borderRadius: 24, padding: 24, gap: 10, alignItems: "center" },
  sheetTitle: { fontFamily: FONT_DISPLAY, fontSize: 24, color: colors.onSurface, textAlign: "center" },
  hint: { fontFamily: FONT_TEXT, fontSize: 13, color: colors.muted, textAlign: "center" },
  stationBtn: { flex: 1, height: 110, borderRadius: 18, backgroundColor: colors.surfaceInverse, alignItems: "center", justifyContent: "center", gap: 8, borderWidth: 3, borderColor: colors.surfaceInverse },
  stationBtnOn: { backgroundColor: colors.success, borderColor: colors.brandSecondary },
  stationBtnText: { fontFamily: FONT_DISPLAY, fontSize: 22, color: colors.onSurfaceInverse },
  successIcon: { width: 72, height: 72, borderRadius: 36, backgroundColor: colors.success, alignItems: "center", justifyContent: "center" },
  orderNum: { fontFamily: FONT_DISPLAY, fontSize: 40, color: colors.onSurface },
}));
