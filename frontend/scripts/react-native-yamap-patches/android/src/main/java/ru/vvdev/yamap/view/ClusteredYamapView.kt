package ru.vvdev.yamap.view

import android.content.Context
import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.graphics.PointF
import android.graphics.RectF
import android.graphics.Typeface
import com.facebook.react.bridge.Arguments
import com.facebook.react.bridge.ReactContext
import com.facebook.react.bridge.WritableArray
import com.facebook.react.bridge.WritableMap
import com.facebook.react.uimanager.events.RCTEventEmitter
import com.yandex.mapkit.geometry.Point
import com.yandex.mapkit.map.Cluster
import com.yandex.mapkit.map.ClusterListener
import com.yandex.mapkit.map.ClusterTapListener
import com.yandex.mapkit.map.IconStyle
import com.yandex.mapkit.map.MapObject
import com.yandex.mapkit.map.MapObjectTapListener
import com.yandex.mapkit.map.PlacemarkMapObject
import com.yandex.runtime.image.ImageProvider
import ru.vvdev.yamap.utils.Callback
import ru.vvdev.yamap.utils.ImageLoader.DownloadImageBitmap
import kotlin.math.ceil

class ClusteredYamapView(context: Context?) : YamapView(context), ClusterListener,
    ClusterTapListener, MapObjectTapListener {
    private data class ClusteredMarkerPayload(
        val point: Point,
        val iconKey: String,
        val data: HashMap<String, Any?>?,
    )

    private val clusterCollection = mapWindow.map.mapObjects.addClusterizedPlacemarkCollection(this)
    private var clusterColor = 0
    private var pointsList = ArrayList<Point>()
    private val placemarks = ArrayList<PlacemarkMapObject>()
    private val placemarkPayloads = ArrayList<ClusteredMarkerPayload>()
    private val markerIconSources = HashMap<String, String>()
    private val markerIconBitmaps = HashMap<String, Bitmap>()
    private val markerDisplayBitmaps = HashMap<String, Bitmap>()
    private var markerSizeDp = DEFAULT_MARKER_SIZE_DP

    fun setClusteredMarkers(markers: List<Any>?) {
        clusterCollection.clear()
        placemarks.clear()
        placemarkPayloads.clear()
        pointsList.clear()

        if (markers.isNullOrEmpty()) {
            return
        }

        val nextPoints = ArrayList<Point>()
        val nextPayloads = ArrayList<ClusteredMarkerPayload>()

        for (markerLike in markers) {
            val marker = markerLike as? HashMap<*, *> ?: continue
            val pointInfo = marker["point"] as? HashMap<*, *> ?: continue
            val latitude = (pointInfo["lat"] as? Number)?.toDouble() ?: continue
            val longitude = (pointInfo["lon"] as? Number)?.toDouble() ?: continue
            val iconKey = marker["iconKey"] as? String ?: DEFAULT_ICON_KEY
            @Suppress("UNCHECKED_CAST")
            val data = marker["data"] as? HashMap<String, Any?>

            val point = Point(latitude, longitude)
            nextPoints.add(point)
            nextPayloads.add(
                ClusteredMarkerPayload(
                    point = point,
                    iconKey = iconKey,
                    data = data,
                )
            )
        }

        if (nextPoints.isEmpty()) {
            return
        }

        val placeholderBitmap = getMarkerBitmap(nextPayloads.first().iconKey)
        val placemarkObjects = clusterCollection.addPlacemarks(
            nextPoints,
            ImageProvider.fromBitmap(placeholderBitmap),
            markerIconStyle(),
        )

        pointsList.addAll(nextPoints)
        placemarks.addAll(placemarkObjects)
        placemarkPayloads.addAll(nextPayloads)

        for (placemark in placemarkObjects) {
            placemark.addTapListener(this)
        }

        applyMarkerIcons()
        clusterCollection.clusterPlacemarks(50.0, 12)
    }

    fun setClusteredMarkerIcons(icons: HashMap<String, String>) {
        markerIconSources.clear()
        markerIconBitmaps.clear()
        markerDisplayBitmaps.clear()
        markerIconSources.putAll(icons)

        for ((iconKey, iconSource) in markerIconSources) {
            DownloadImageBitmap(context, iconSource, object : Callback<Bitmap?> {
                override fun invoke(arg: Bitmap?) {
                    if (arg == null || markerIconSources[iconKey] != iconSource) {
                        return
                    }

                    markerIconBitmaps[iconKey] = arg
                    markerDisplayBitmaps.remove(iconKey)
                    applyMarkerIcons()
                }
            })
        }

        applyMarkerIcons()
    }

    fun clearClusteredMarkerIcons() {
        markerIconSources.clear()
        markerIconBitmaps.clear()
        markerDisplayBitmaps.clear()
        applyMarkerIcons()
    }

    fun setClustersColor(color: Int) {
        clusterColor = color
        clusterCollection.clusterPlacemarks(50.0, 12)
    }

    fun setMarkerSize(markerSize: Float) {
        val resolvedMarkerSize = if (markerSize > 0f) markerSize else DEFAULT_MARKER_SIZE_DP
        if (markerSizeDp == resolvedMarkerSize) {
            return
        }

        markerSizeDp = resolvedMarkerSize
        markerDisplayBitmaps.clear()
        applyMarkerIcons()
    }

    private fun markerIconStyle(): IconStyle {
        val iconStyle = IconStyle()
        iconStyle.setScale(1.0f)
        iconStyle.setAnchor(PointF(0.5f, 0.5f))
        return iconStyle
    }

    private fun applyMarkerIcons() {
        val markerCount = minOf(placemarks.size, placemarkPayloads.size)
        for (index in 0 until markerCount) {
            val placemark = placemarks[index]
            val payload = placemarkPayloads[index]
            placemark.setIcon(ImageProvider.fromBitmap(getMarkerBitmap(payload.iconKey)))
            placemark.setIconStyle(markerIconStyle())
        }
    }

    private fun getMarkerBitmap(iconKey: String): Bitmap {
        markerDisplayBitmaps[iconKey]?.let { return it }

        val originalBitmap = markerIconBitmaps[iconKey]
        if (originalBitmap != null) {
            val resizedBitmap = resizeMarkerBitmap(originalBitmap)
            markerDisplayBitmaps[iconKey] = resizedBitmap
            return resizedBitmap
        }

        return createFallbackMarkerBitmap(iconKey)
    }

    private fun resizeMarkerBitmap(bitmap: Bitmap): Bitmap {
        val targetSize = ceil(markerSizeDp * resources.displayMetrics.density.toDouble()).toInt()
        if (bitmap.width == targetSize && bitmap.height == targetSize) {
            return bitmap
        }

        return Bitmap.createScaledBitmap(bitmap, targetSize, targetSize, true)
    }

    override fun addFeature(child: android.view.View?, index: Int) {
        // Clustered markers are native-only and no longer mount React marker children.
    }

    override fun removeChild(index: Int) {
        // Clustered markers are native-only and no longer mount React marker children.
    }

    override fun onClusterAdded(cluster: Cluster) {
        cluster.appearance.setIcon(TextImageProvider(cluster.size.toString()))
        cluster.addClusterTapListener(this)
    }

    override fun onClusterTap(cluster: Cluster): Boolean {
        val points = ArrayList<Point?>()
        for (placemark in cluster.placemarks) {
            points.add(placemark.geometry)
        }
        fitMarkers(points)
        return true
    }

    override fun onMapObjectTap(mapObject: MapObject, point: Point): Boolean {
        val placemark = mapObject as? PlacemarkMapObject ?: return true
        val index = placemarks.indexOf(placemark)
        if (index < 0 || index >= placemarkPayloads.size) {
            return true
        }

        val payload = placemarkPayloads[index]
        val event = Arguments.createMap()
        val pointData = Arguments.createMap()
        pointData.putDouble("lat", point.latitude)
        pointData.putDouble("lon", point.longitude)
        event.putMap("point", pointData)
        event.putString("iconKey", payload.iconKey)
        payload.data?.let { event.putMap("data", toWritableMap(it)) }
        (context as ReactContext).getJSModule(RCTEventEmitter::class.java).receiveEvent(
            id,
            "onMarkerPress",
            event,
        )

        return true
    }

    private fun toWritableMap(source: HashMap<String, Any?>): WritableMap {
        val result = Arguments.createMap()
        for ((key, value) in source) {
            if (key == null) {
                continue
            }

            putValue(result, key, value)
        }

        return result
    }

    private fun toWritableArray(source: ArrayList<*>): WritableArray {
        val result = Arguments.createArray()
        for (value in source) {
            pushValue(result, value)
        }

        return result
    }

    private fun putValue(target: WritableMap, key: String, value: Any?) {
        when (value) {
            null -> target.putNull(key)
            is Boolean -> target.putBoolean(key, value)
            is Double -> target.putDouble(key, value)
            is Float -> target.putDouble(key, value.toDouble())
            is Int -> target.putInt(key, value)
            is Long -> target.putDouble(key, value.toDouble())
            is Number -> target.putDouble(key, value.toDouble())
            is String -> target.putString(key, value)
            is HashMap<*, *> -> {
                @Suppress("UNCHECKED_CAST")
                target.putMap(key, toWritableMap(value as HashMap<String, Any?>))
            }
            is ArrayList<*> -> target.putArray(key, toWritableArray(value))
            else -> target.putString(key, value.toString())
        }
    }

    private fun pushValue(target: WritableArray, value: Any?) {
        when (value) {
            null -> target.pushNull()
            is Boolean -> target.pushBoolean(value)
            is Double -> target.pushDouble(value)
            is Float -> target.pushDouble(value.toDouble())
            is Int -> target.pushInt(value)
            is Long -> target.pushDouble(value.toDouble())
            is Number -> target.pushDouble(value.toDouble())
            is String -> target.pushString(value)
            is HashMap<*, *> -> {
                @Suppress("UNCHECKED_CAST")
                target.pushMap(toWritableMap(value as HashMap<String, Any?>))
            }
            is ArrayList<*> -> target.pushArray(toWritableArray(value))
            else -> target.pushString(value.toString())
        }
    }

    private inner class TextImageProvider(private val text: String) : ImageProvider() {
        override fun getId(): String {
            return "text_$text"
        }

        override fun getImage(): Bitmap {
            val density = resources.displayMetrics.density
            val textPaint = Paint()
            textPaint.textSize = FONT_SIZE * density
            textPaint.textAlign = Paint.Align.CENTER
            textPaint.style = Paint.Style.FILL
            textPaint.isAntiAlias = true
            textPaint.color = Color.WHITE
            textPaint.typeface = Typeface.create("sans-serif-medium", Typeface.NORMAL)

            val bubbleHeight = BUBBLE_HEIGHT * density
            val horizontalPadding = HORIZONTAL_PADDING * density
            val borderWidth = BORDER_WIDTH * density
            val bubbleWidth = maxOf(bubbleHeight, textPaint.measureText(text) + horizontalPadding * 2)

            val width = ceil(bubbleWidth + borderWidth * 2).toInt()
            val height = ceil(bubbleHeight + borderWidth * 2).toInt()
            val bubbleRect = RectF(
                borderWidth,
                borderWidth,
                width - borderWidth,
                height - borderWidth
            )

            val bitmap = Bitmap.createBitmap(width, height, Bitmap.Config.ARGB_8888)
            val canvas = Canvas(bitmap)

            val fillPaint = Paint()
            fillPaint.isAntiAlias = true
            fillPaint.style = Paint.Style.FILL
            fillPaint.color = if (clusterColor != 0) clusterColor else Color.parseColor("#00A0E3")

            val strokePaint = Paint()
            strokePaint.isAntiAlias = true
            strokePaint.style = Paint.Style.STROKE
            strokePaint.strokeWidth = borderWidth
            strokePaint.color = Color.argb(242, 255, 255, 255)

            val cornerRadius = bubbleHeight / 2
            canvas.drawRoundRect(bubbleRect, cornerRadius, cornerRadius, fillPaint)
            canvas.drawRoundRect(bubbleRect, cornerRadius, cornerRadius, strokePaint)

            val textMetrics = textPaint.fontMetrics

            canvas.drawText(
                text,
                bubbleRect.centerX(),
                bubbleRect.centerY() - (textMetrics.ascent + textMetrics.descent) / 2,
                textPaint
            )

            return bitmap
        }
    }

    private fun createFallbackMarkerBitmap(iconKey: String): Bitmap {
        val density = resources.displayMetrics.density
        val outerSize = markerSizeDp * density
        val innerSize = outerSize * (CDEK_PICKUP_MARKER_INNER_SIZE / CDEK_PICKUP_MARKER_OUTER_SIZE)
        val bitmap = Bitmap.createBitmap(ceil(outerSize.toDouble()).toInt(), ceil(outerSize.toDouble()).toInt(), Bitmap.Config.ARGB_8888)
        val canvas = Canvas(bitmap)

        val outerPaint = Paint()
        outerPaint.isAntiAlias = true
        outerPaint.style = Paint.Style.FILL
        outerPaint.color = Color.parseColor("#00A0E3")

        val innerPaint = Paint()
        innerPaint.isAntiAlias = true
        innerPaint.style = Paint.Style.FILL
        innerPaint.color = if (iconKey == "yandex") {
            Color.parseColor("#FF5A1F")
        } else {
            Color.parseColor("#10B65A")
        }

        val strokePaint = Paint()
        strokePaint.isAntiAlias = true
        strokePaint.style = Paint.Style.STROKE
        strokePaint.strokeWidth = 2f * density
        strokePaint.color = Color.WHITE

        canvas.drawCircle(outerSize / 2f, outerSize / 2f, outerSize / 2f, outerPaint)
        canvas.drawCircle(outerSize / 2f, outerSize / 2f, innerSize / 2f, innerPaint)
        canvas.drawCircle(outerSize / 2f, outerSize / 2f, innerSize / 2f, strokePaint)

        val textPaint = Paint()
        textPaint.isAntiAlias = true
        textPaint.color = Color.WHITE
        textPaint.textAlign = Paint.Align.CENTER
        val fontScale = outerSize / (CDEK_PICKUP_MARKER_OUTER_SIZE * density)
        textPaint.textSize = if (iconKey == "yandex") 10f * density * fontScale else 9f * density * fontScale
        textPaint.typeface = Typeface.create(
            "sans-serif-medium",
            if (iconKey == "yandex") Typeface.BOLD else Typeface.ITALIC,
        )

        val label = if (iconKey == "yandex") "YA" else "CDEK"
        val textMetrics = textPaint.fontMetrics
        canvas.drawText(
            label,
            outerSize / 2f,
            outerSize / 2f - (textMetrics.ascent + textMetrics.descent) / 2f,
            textPaint,
        )

        return bitmap
    }

    companion object {
        private const val DEFAULT_ICON_KEY = "cdek"
        private const val FONT_SIZE = 17f
        private const val BUBBLE_HEIGHT = 42f
        private const val HORIZONTAL_PADDING = 14f
        private const val BORDER_WIDTH = 2f
        private const val DEFAULT_MARKER_SIZE_DP = 34f
        private const val CDEK_PICKUP_MARKER_OUTER_SIZE = 34f
        private const val CDEK_PICKUP_MARKER_INNER_SIZE = 28f
    }
}
