package ru.vvdev.yamap

import android.content.pm.PackageManager
import com.facebook.react.bridge.Callback
import com.facebook.react.bridge.Promise
import com.facebook.react.bridge.ReactApplicationContext
import com.facebook.react.bridge.ReactContextBaseJavaModule
import com.facebook.react.bridge.ReactMethod
import com.facebook.react.bridge.UiThreadUtil
import com.facebook.react.bridge.WritableMap
import com.facebook.react.modules.core.DeviceEventManagerModule
import com.yandex.mapkit.MapKitFactory
import com.yandex.runtime.i18n.I18nManagerFactory

class RNYamapModule internal constructor(context: ReactApplicationContext?) :
    ReactContextBaseJavaModule(context) {
    init {
        Companion.context = context
    }

    override fun getName(): String {
        return REACT_CLASS
    }

    override fun getConstants(): Map<String, Any>? {
        return HashMap()
    }

    private fun resolveApiKey(providedApiKey: String?): String? {
        val normalized = providedApiKey?.trim().orEmpty()
        if (normalized.isNotEmpty()) {
            return normalized
        }

        val reactContext = context ?: return null
        return try {
            val appInfo = reactContext.packageManager.getApplicationInfo(
                reactContext.packageName,
                PackageManager.GET_META_DATA
            )
            appInfo.metaData
                ?.getString(MAPKIT_API_KEY_MANIFEST_KEY)
                ?.trim()
                ?.takeIf { it.isNotEmpty() }
        } catch (_: Throwable) {
            null
        }
    }

    @ReactMethod
    fun init(apiKey: String?, promise: Promise) {
        UiThreadUtil.runOnUiThread(Thread(Runnable {
            var apiKeyException: Throwable? = null
            try {
                val resolvedApiKey = resolveApiKey(apiKey)
                    ?: throw IllegalStateException("Missing Yandex MapKit API key")

                // In case when android application reloads during development
                // MapKitFactory is already initialized
                // And setting api key leads to crash
                try {
                    MapKitFactory.setApiKey(resolvedApiKey)
                } catch (exception: Throwable) {
                    apiKeyException = exception
                }

                MapKitFactory.initialize(context)
                MapKitFactory.getInstance().onStart()
                promise.resolve(null)
            } catch (exception: Exception) {
                if (apiKeyException != null) {
                    promise.reject(apiKeyException)
                    return@Runnable
                }
                promise.reject(exception)
            }
        }))
    }

    @ReactMethod
    fun setLocale(locale: String?, successCb: Callback, errorCb: Callback?) {
        UiThreadUtil.runOnUiThread(Thread {
            MapKitFactory.setLocale(locale)
            successCb.invoke()
        })
    }

    @ReactMethod
    fun getLocale(successCb: Callback, errorCb: Callback?) {
        UiThreadUtil.runOnUiThread(Thread {
            val locale = I18nManagerFactory.getLocale()
            successCb.invoke(locale)
        })
    }

    @ReactMethod
    fun resetLocale(successCb: Callback, errorCb: Callback?) {
        UiThreadUtil.runOnUiThread(Thread {
            I18nManagerFactory.setLocale(null)
            successCb.invoke()
        })
    }

    companion object {
        private const val REACT_CLASS = "yamap"
        private const val MAPKIT_API_KEY_MANIFEST_KEY = "YANDEX_MAPKIT_API_KEY"

        private var context: ReactApplicationContext? = null

        private fun emitDeviceEvent(eventName: String, eventData: WritableMap?) {
            context!!.getJSModule(
                DeviceEventManagerModule.RCTDeviceEventEmitter::class.java
            ).emit(eventName, eventData)
        }
    }
}
