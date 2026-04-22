import { useState } from "react"
import { NativeSyntheticEvent, Text, View } from "react-native"
import { Marker, type Point, YaMap } from "react-native-yamap"

import { DEFAULT_POINT } from "@/components/maps/checkout-map-card.native.constants"
import { checkoutMapCardNativeStyles } from "@/components/maps/checkout-map-card.native.styles"

export default function CheckoutMapCard() {
    const [marker, setMarker] = useState<Point | undefined>(undefined)

    const handleMapLongPress = (event: NativeSyntheticEvent<Point>) => {
        setMarker(event.nativeEvent)
    }

    return (
        <View style={checkoutMapCardNativeStyles.container}>
            <Text style={checkoutMapCardNativeStyles.title}>Yandex Map</Text>

            <View style={checkoutMapCardNativeStyles.mapWrapper}>
                <YaMap
                    style={checkoutMapCardNativeStyles.map}
                    initialRegion={{
                        lat: DEFAULT_POINT.lat,
                        lon: DEFAULT_POINT.lon,
                        zoom: 14,
                        azimuth: 0,
                        tilt: 0,
                    }}
                    onMapLongPress={handleMapLongPress}
                    scrollGesturesEnabled
                    showUserPosition={false}
                    zoomGesturesEnabled
                >
                    <Marker point={marker ?? DEFAULT_POINT} />
                </YaMap>
            </View>
        </View>
    )
}
