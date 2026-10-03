# Proguard rules for eBay Draft Commander Android Wrapper
-keepattributes JavascriptInterface
-keepclassmembers class * {
    @android.webkit.JavascriptInterface <methods>;
}
