#import <React/RCTComponent.h>
#import <React/UIView+React.h>

#import <MapKit/MapKit.h>
#import "../Converter/RCTConvert+Yamap.m"
@import YandexMapsMobile;

#ifndef MAX
#import <NSObjCRuntime.h>
#endif

#import "RNCYMView.h"

#define UIColorFromRGB(rgbValue) [UIColor colorWithRed:((float)((rgbValue & 0xFF0000) >> 16))/255.0 green:((float)((rgbValue & 0xFF00) >> 8))/255.0 blue:((float)(rgbValue & 0xFF))/255.0 alpha:1.0]

static NSString *const RNCYMDefaultIconKey = @"cdek";
static CGFloat const RNCYMDefaultClusteredMarkerDisplaySize = 34.0;

static inline void RNCYMDispatchToMain(dispatch_block_t block) {
    if ([NSThread isMainThread]) {
        block();
    } else {
        dispatch_async(dispatch_get_main_queue(), block);
    }
}

static inline NSString *RNCYMThreadName(void) {
    return [NSThread isMainThread] ? @"main" : @"background";
}

static inline NSTimeInterval RNCYMNow(void) {
    return [[NSDate date] timeIntervalSince1970];
}

@interface RNYMView (RNCYMInheritedCallbacks)
- (void)onCameraPositionChangedWithMap:(nonnull YMKMap*)map
                        cameraPosition:(nonnull YMKCameraPosition*)cameraPosition
                    cameraUpdateReason:(YMKCameraUpdateReason)cameraUpdateReason
                              finished:(BOOL)finished;
- (void)onMapLoadedWithStatistics:(YMKMapLoadStatistics*)statistics;
@end

@implementation RNCYMView {
    YMKMasstransitSession *masstransitSession;
    YMKMasstransitSession *walkSession;
    YMKMasstransitRouter *masstransitRouter;
    YMKDrivingRouter* drivingRouter;
    YMKDrivingSession* drivingSession;
    YMKPedestrianRouter *pedestrianRouter;
    YMKTransitOptions *transitOptions;
    YMKMasstransitSessionRouteHandler routeHandler;
    NSMutableArray *routes;
    NSMutableArray *currentRouteInfo;
    NSMutableArray<YMKRequestPoint *>* lastKnownRoutePoints;
    YMKUserLocationView* userLocationView;
    NSMutableDictionary *vehicleColors;
    UIImage* userLocationImage;
    NSArray *acceptVehicleTypes;
    YMKUserLocationLayer *userLayer;
    UIColor* userLocationAccuracyFillColor;
    UIColor* userLocationAccuracyStrokeColor;
    float userLocationAccuracyStrokeWidth;
    YMKClusterizedPlacemarkCollection *clusterCollection;
    UIColor* clusterColor;
    NSMutableArray<YMKPlacemarkMapObject *>* placemarks;
    NSMutableArray<NSDictionary *> *placemarkPayloads;
    NSMutableDictionary<NSString *, NSString *> *clusteredMarkerIconSources;
    NSMutableDictionary<NSString *, UIImage *> *clusteredMarkerOriginalIconCache;
    NSMutableDictionary<NSString *, UIImage *> *clusteredMarkerDisplayIconCache;
    CGFloat clusteredMarkerDisplaySize;
    NSUInteger clusteredMarkersApplyToken;
    NSUInteger clusterAddedLogCount;
    NSUInteger cameraPositionEventCount;
    NSUInteger mapLoadedEventCount;
    Boolean initializedRegion;
}

- (instancetype)init {
    NSLog(@"[delivery-flow][yamap] RNCYMView init requested thread=%@", RNCYMThreadName());
    self = [super init];
    NSLog(@"[delivery-flow][yamap] RNCYMView super init returned self=%p thread=%@", self, RNCYMThreadName());
    placemarks = [[NSMutableArray alloc] init];
    placemarkPayloads = [[NSMutableArray alloc] init];
    clusteredMarkerIconSources = [[NSMutableDictionary alloc] init];
    clusteredMarkerOriginalIconCache = [[NSMutableDictionary alloc] init];
    clusteredMarkerDisplayIconCache = [[NSMutableDictionary alloc] init];
    clusteredMarkerDisplaySize = RNCYMDefaultClusteredMarkerDisplaySize;
    clusteredMarkersApplyToken = 0;
    clusterAddedLogCount = 0;
    cameraPositionEventCount = 0;
    mapLoadedEventCount = 0;
    clusterColor = nil;
    NSLog(@"[delivery-flow][yamap] cluster collection creation started thread=%@", RNCYMThreadName());
    clusterCollection = [self.mapWindow.map.mapObjects addClusterizedPlacemarkCollectionWithClusterListener:self];
    NSLog(@"[delivery-flow][yamap] cluster collection creation finished thread=%@", RNCYMThreadName());
    initializedRegion = NO;
    NSLog(@"[delivery-flow][yamap] RNCYMView initialized thread=%@", RNCYMThreadName());
    return self;
}

- (void)setClusterColor:(UIColor *)color {
    if (![NSThread isMainThread]) {
        RNCYMDispatchToMain(^{
            [self setClusterColor:color];
        });
        return;
    }

    clusterColor = color;
    NSLog(@"[delivery-flow][yamap] cluster color updated thread=%@", RNCYMThreadName());
    [clusterCollection clusterPlacemarksWithClusterRadius:50 minZoom:12];
}

- (void)setClusteredMarkerIcons:(NSDictionary<NSString *,NSString *> *)icons {
    NSDictionary<NSString *, NSString *> *iconsSnapshot = [icons isKindOfClass:[NSDictionary class]]
        ? [icons copy]
        : nil;

    if (![NSThread isMainThread]) {
        RNCYMDispatchToMain(^{
            [self setClusteredMarkerIcons:iconsSnapshot];
        });
        return;
    }

    [clusteredMarkerIconSources removeAllObjects];
    [clusteredMarkerOriginalIconCache removeAllObjects];
    [clusteredMarkerDisplayIconCache removeAllObjects];

    NSLog(@"[delivery-flow][yamap] marker icons update started count=%lu thread=%@",
          (unsigned long)iconsSnapshot.count,
          RNCYMThreadName());

    if (![iconsSnapshot isKindOfClass:[NSDictionary class]]) {
        [self applyClusteredMarkerIcons];
        return;
    }

    [clusteredMarkerIconSources addEntriesFromDictionary:iconsSnapshot];

    for (NSString *iconKey in clusteredMarkerIconSources) {
        NSString *source = clusteredMarkerIconSources[iconKey];
        [self loadClusteredMarkerIconForKey:iconKey source:source];
    }
}

- (void)applyClusteredMarkersOnMain:(NSArray *)markers applyToken:(NSUInteger)applyToken {
    NSAssert([NSThread isMainThread], @"Clustered Yamap markers must be applied on the main thread.");
    NSTimeInterval startedAt = RNCYMNow();
    NSUInteger inputCount = [markers isKindOfClass:[NSArray class]] ? markers.count : 0;
    NSLog(@"[delivery-flow][yamap] clustered markers apply started token=%lu inputCount=%lu thread=%@",
          (unsigned long)applyToken,
          (unsigned long)inputCount,
          RNCYMThreadName());

    [placemarks removeAllObjects];
    [placemarkPayloads removeAllObjects];
    [clusterCollection clear];

    if (![markers isKindOfClass:[NSArray class]] || markers.count == 0) {
        NSLog(@"[delivery-flow][yamap] clustered markers cleared token=%lu durationMs=%.0f",
              (unsigned long)applyToken,
              (RNCYMNow() - startedAt) * 1000.0);
        return;
    }

    NSMutableArray<YMKPoint *> *points = [[NSMutableArray alloc] init];
    NSMutableArray<NSDictionary *> *normalizedMarkers = [[NSMutableArray alloc] init];
    NSMutableArray<NSString *> *orderedIconKeys = [[NSMutableArray alloc] init];
    NSMutableDictionary<NSString *, NSMutableArray<YMKPoint *> *> *pointsByIconKey = [[NSMutableDictionary alloc] init];
    NSMutableDictionary<NSString *, NSMutableArray<NSDictionary *> *> *payloadsByIconKey = [[NSMutableDictionary alloc] init];

    for (id markerLike in markers) {
        if (![markerLike isKindOfClass:[NSDictionary class]]) {
            continue;
        }

        NSDictionary *marker = (NSDictionary *)markerLike;
        NSDictionary *pointInfo = marker[@"point"];
        if (![pointInfo isKindOfClass:[NSDictionary class]]) {
            continue;
        }

        NSNumber *latitude = pointInfo[@"lat"];
        NSNumber *longitude = pointInfo[@"lon"];
        if (![latitude isKindOfClass:[NSNumber class]] || ![longitude isKindOfClass:[NSNumber class]]) {
            continue;
        }

        NSString *iconKey = [marker[@"iconKey"] isKindOfClass:[NSString class]]
            ? marker[@"iconKey"]
            : RNCYMDefaultIconKey;
        NSDictionary *data = [marker[@"data"] isKindOfClass:[NSDictionary class]]
            ? marker[@"data"]
            : nil;

        YMKPoint *point = [YMKPoint pointWithLatitude:[latitude doubleValue] longitude:[longitude doubleValue]];
        NSDictionary *normalizedMarker = @{
            @"point": @{
                @"lat": latitude,
                @"lon": longitude,
            },
            @"iconKey": iconKey,
            @"data": data ?: @{},
        };
        NSMutableArray<YMKPoint *> *iconPoints = pointsByIconKey[iconKey];
        NSMutableArray<NSDictionary *> *iconPayloads = payloadsByIconKey[iconKey];

        if (iconPoints == nil || iconPayloads == nil) {
            iconPoints = [[NSMutableArray alloc] init];
            iconPayloads = [[NSMutableArray alloc] init];
            pointsByIconKey[iconKey] = iconPoints;
            payloadsByIconKey[iconKey] = iconPayloads;
            [orderedIconKeys addObject:iconKey];
        }

        [points addObject:point];
        [normalizedMarkers addObject:normalizedMarker];
        [iconPoints addObject:point];
        [iconPayloads addObject:normalizedMarker];
    }

    if (points.count == 0) {
        NSLog(@"[delivery-flow][yamap] clustered markers normalized empty token=%lu inputCount=%lu durationMs=%.0f",
              (unsigned long)applyToken,
              (unsigned long)inputCount,
              (RNCYMNow() - startedAt) * 1000.0);
        return;
    }

    NSLog(@"[delivery-flow][yamap] clustered markers normalized token=%lu normalizedCount=%lu durationMs=%.0f",
          (unsigned long)applyToken,
          (unsigned long)points.count,
          (RNCYMNow() - startedAt) * 1000.0);

    NSTimeInterval addStartedAt = RNCYMNow();
    NSLog(@"[delivery-flow][yamap] clustered markers addPlacemarks started token=%lu count=%lu iconGroups=%lu",
          (unsigned long)applyToken,
          (unsigned long)points.count,
          (unsigned long)orderedIconKeys.count);

    NSUInteger addedPlacemarkCount = 0;
    for (NSString *iconKey in orderedIconKeys) {
        NSArray<YMKPoint *> *iconPoints = pointsByIconKey[iconKey];
        NSArray<NSDictionary *> *iconPayloads = payloadsByIconKey[iconKey];

        if (iconPoints.count == 0 || iconPayloads.count == 0) {
            continue;
        }

        UIImage *iconImage = [self markerImageForIconKey:iconKey];
        NSArray<YMKPlacemarkMapObject *>* newPlacemarks = [clusterCollection addPlacemarksWithPoints:iconPoints image:iconImage style:[self markerIconStyle]];
        [placemarks addObjectsFromArray:newPlacemarks];
        [placemarkPayloads addObjectsFromArray:iconPayloads];
        addedPlacemarkCount += newPlacemarks.count;
    }

    NSLog(@"[delivery-flow][yamap] clustered markers addPlacemarks finished token=%lu count=%lu durationMs=%.0f",
          (unsigned long)applyToken,
          (unsigned long)addedPlacemarkCount,
          (RNCYMNow() - addStartedAt) * 1000.0);

    for (YMKPlacemarkMapObject *placemark in placemarks) {
        [placemark addTapListenerWithTapListener:self];
    }

    NSTimeInterval clusterStartedAt = RNCYMNow();
    NSLog(@"[delivery-flow][yamap] clusterPlacemarks started token=%lu count=%lu",
          (unsigned long)applyToken,
          (unsigned long)placemarks.count);
    [clusterCollection clusterPlacemarksWithClusterRadius:50 minZoom:12];
    NSLog(@"[delivery-flow][yamap] clusterPlacemarks finished token=%lu durationMs=%.0f totalDurationMs=%.0f",
          (unsigned long)applyToken,
          (RNCYMNow() - clusterStartedAt) * 1000.0,
          (RNCYMNow() - startedAt) * 1000.0);
}

- (void)setClusteredMarkers:(NSArray *)markers {
    NSArray *markersSnapshot = [markers isKindOfClass:[NSArray class]] ? [markers copy] : nil;
    __block NSUInteger applyToken = 0;

    @synchronized (self) {
        clusteredMarkersApplyToken += 1;
        applyToken = clusteredMarkersApplyToken;
    }

    NSLog(@"[delivery-flow][yamap] clustered markers apply queued token=%lu inputCount=%lu callerThread=%@",
          (unsigned long)applyToken,
          (unsigned long)markersSnapshot.count,
          RNCYMThreadName());

    dispatch_async(dispatch_get_main_queue(), ^{
        @synchronized (self) {
            if (applyToken != self->clusteredMarkersApplyToken) {
                NSLog(@"[delivery-flow][yamap] clustered markers apply skipped stale token=%lu latestToken=%lu",
                      (unsigned long)applyToken,
                      (unsigned long)self->clusteredMarkersApplyToken);
                return;
            }
        }

        [self applyClusteredMarkersOnMain:markersSnapshot applyToken:applyToken];
    });
}

- (void)setMarkerSize:(CGFloat)markerSize {
    if (![NSThread isMainThread]) {
        RNCYMDispatchToMain(^{
            [self setMarkerSize:markerSize];
        });
        return;
    }

    CGFloat resolvedMarkerSize = markerSize > 0.0 ? markerSize : RNCYMDefaultClusteredMarkerDisplaySize;
    if (fabs(clusteredMarkerDisplaySize - resolvedMarkerSize) < 0.5) {
        return;
    }

    clusteredMarkerDisplaySize = resolvedMarkerSize;
    [clusteredMarkerDisplayIconCache removeAllObjects];
    NSLog(@"[delivery-flow][yamap] marker size updated size=%.2f thread=%@",
          clusteredMarkerDisplaySize,
          RNCYMThreadName());
    [self applyClusteredMarkerIcons];
}

- (void)onObjectRemovedWithView:(nonnull YMKUserLocationView *)view {
}

- (void)onMapTapWithMap:(nonnull YMKMap *)map
                  point:(nonnull YMKPoint *)point {
    NSLog(@"[delivery-flow][yamap] map tap lat=%.6f lon=%.6f thread=%@",
          point.latitude,
          point.longitude,
          RNCYMThreadName());
    if (self.onMapPress) {
        NSDictionary *data = @{
            @"lat": @(point.latitude),
            @"lon": @(point.longitude),
        };
        self.onMapPress(data);
    }
}

- (void)onMapLongTapWithMap:(nonnull YMKMap *)map
                      point:(nonnull YMKPoint *)point {
    NSLog(@"[delivery-flow][yamap] map long tap lat=%.6f lon=%.6f thread=%@",
          point.latitude,
          point.longitude,
          RNCYMThreadName());
    if (self.onMapLongPress) {
        NSDictionary *data = @{
            @"lat": @(point.latitude),
            @"lon": @(point.longitude),
        };
        self.onMapLongPress(data);
    }
}

+ (UIColor*)colorFromHexString:(NSString*)hexString {
    unsigned rgbValue = 0;
    NSScanner *scanner = [NSScanner scannerWithString:hexString];
    [scanner setScanLocation:1];
    [scanner scanHexInt:&rgbValue];
    return [UIColor colorWithRed:((rgbValue & 0xFF0000) >> 16)/255.0 green:((rgbValue & 0xFF00) >> 8)/255.0 blue:(rgbValue & 0xFF)/255.0 alpha:1.0];
}

+ (NSString*)hexStringFromColor:(UIColor *)color {
    const CGFloat *components = CGColorGetComponents(color.CGColor);
    CGFloat r = components[0];
    CGFloat g = components[1];
    CGFloat b = components[2];
    return [NSString stringWithFormat:@"#%02lX%02lX%02lX", lroundf(r * 255), lroundf(g * 255), lroundf(b * 255)];
}

- (YMKIconStyle *)markerIconStyle {
    YMKIconStyle *iconStyle = [[YMKIconStyle alloc] init];
    [iconStyle setScale:@(1.0f)];
    return iconStyle;
}

- (UIColor *)clusteredMarkerOuterColor {
    return [RNCYMView colorFromHexString:@"#00A0E3"];
}

- (UIColor *)clusteredMarkerInnerColorForIconKey:(NSString *)iconKey {
    if ([iconKey isEqualToString:@"yandex"]) {
        return [RNCYMView colorFromHexString:@"#FF5A1F"];
    }

    return [RNCYMView colorFromHexString:@"#10B65A"];
}

- (NSString *)clusteredMarkerTextForIconKey:(NSString *)iconKey {
    if ([iconKey isEqualToString:@"yandex"]) {
        return @"YA";
    }

    return @"CDEK";
}

- (UIFont *)clusteredMarkerFontForIconKey:(NSString *)iconKey {
    if ([iconKey isEqualToString:@"yandex"]) {
        return [UIFont systemFontOfSize:10.0 weight:UIFontWeightBlack];
    }

    return [UIFont italicSystemFontOfSize:9.0];
}

- (UIImage *)fallbackMarkerImageForIconKey:(NSString *)iconKey {
    NSString *resolvedIconKey = iconKey ?: RNCYMDefaultIconKey;
    NSString *text = [self clusteredMarkerTextForIconKey:resolvedIconKey];
    CGFloat outerSize = clusteredMarkerDisplaySize;
    CGFloat innerSize = outerSize * (28.0 / 34.0);
    CGRect outerRect = CGRectMake(0.0, 0.0, outerSize, outerSize);
    CGRect innerRect = CGRectMake((outerSize - innerSize) / 2.0, (outerSize - innerSize) / 2.0, innerSize, innerSize);
    UIColor *outerColor = [self clusteredMarkerOuterColor];
    UIColor *innerColor = [self clusteredMarkerInnerColorForIconKey:resolvedIconKey];
    CGFloat fontScale = outerSize / 34.0;
    UIFont *font = [resolvedIconKey isEqualToString:@"yandex"]
        ? [UIFont systemFontOfSize:10.0 * fontScale weight:UIFontWeightBlack]
        : [UIFont italicSystemFontOfSize:9.0 * fontScale];

    UIGraphicsBeginImageContextWithOptions(CGSizeMake(outerSize, outerSize), NO, 0.0);

    UIBezierPath *outerPath = [UIBezierPath bezierPathWithOvalInRect:outerRect];
    [outerColor setFill];
    [outerPath fill];

    UIBezierPath *innerPath = [UIBezierPath bezierPathWithOvalInRect:innerRect];
    [innerColor setFill];
    [innerPath fill];
    innerPath.lineWidth = 2.0;
    [[UIColor whiteColor] setStroke];
    [innerPath stroke];

    CGSize textSize = [text sizeWithAttributes:@{
        NSFontAttributeName: font,
    }];
    CGRect textRect = CGRectMake(
        (outerSize - textSize.width) / 2.0,
        (outerSize - textSize.height) / 2.0 - 0.5,
        textSize.width,
        textSize.height
    );
    [text drawInRect:textRect withAttributes:@{
        NSFontAttributeName: font,
        NSForegroundColorAttributeName: UIColor.whiteColor,
    }];

    UIImage *image = UIGraphicsGetImageFromCurrentImageContext();
    UIGraphicsEndImageContext();

    return image;
}

- (UIImage *)resizedMarkerImage:(UIImage *)image {
    if (image == nil) {
        return nil;
    }

    CGSize targetSize = CGSizeMake(clusteredMarkerDisplaySize, clusteredMarkerDisplaySize);
    CGSize imageSize = image.size;
    if (fabs(imageSize.width - targetSize.width) < 0.5 && fabs(imageSize.height - targetSize.height) < 0.5) {
        return image;
    }

    UIGraphicsBeginImageContextWithOptions(targetSize, NO, 0.0);
    [image drawInRect:CGRectMake(0.0, 0.0, targetSize.width, targetSize.height)];
    UIImage *resizedImage = UIGraphicsGetImageFromCurrentImageContext();
    UIGraphicsEndImageContext();

    return resizedImage ?: image;
}

- (UIImage *)markerImageForIconKey:(NSString *)iconKey {
    NSString *resolvedIconKey = iconKey ?: RNCYMDefaultIconKey;
    UIImage *displayImage = clusteredMarkerDisplayIconCache[resolvedIconKey];
    if (displayImage != nil) {
        return displayImage;
    }

    UIImage *originalImage = clusteredMarkerOriginalIconCache[resolvedIconKey];
    if (originalImage != nil) {
        UIImage *resizedImage = [self resizedMarkerImage:originalImage];
        if (resizedImage != nil) {
            clusteredMarkerDisplayIconCache[resolvedIconKey] = resizedImage;
            return resizedImage;
        }
    }

    return [self fallbackMarkerImageForIconKey:resolvedIconKey];
}

- (void)applyClusteredMarkerIconsForIconKey:(NSString *)requestedIconKey {
    if (![NSThread isMainThread]) {
        RNCYMDispatchToMain(^{
            [self applyClusteredMarkerIconsForIconKey:requestedIconKey];
        });
        return;
    }

    NSTimeInterval startedAt = RNCYMNow();
    NSUInteger markerCount = MIN(placemarks.count, placemarkPayloads.count);
    NSUInteger updatedCount = 0;
    NSLog(@"[delivery-flow][yamap] apply marker icons started count=%lu iconKey=%@ thread=%@",
          (unsigned long)markerCount,
          requestedIconKey ?: @"all",
          RNCYMThreadName());

    for (NSUInteger index = 0; index < markerCount; index++) {
        YMKPlacemarkMapObject *placemark = placemarks[index];
        NSDictionary *payload = placemarkPayloads[index];
        NSString *iconKey = [payload[@"iconKey"] isKindOfClass:[NSString class]]
            ? payload[@"iconKey"]
            : RNCYMDefaultIconKey;

        if (requestedIconKey.length > 0 && ![iconKey isEqualToString:requestedIconKey]) {
            continue;
        }

        UIImage *iconImage = [self markerImageForIconKey:iconKey];
        [placemark setIconWithImage:iconImage];
        [placemark setIconStyleWithStyle:[self markerIconStyle]];
        updatedCount += 1;
    }

    NSLog(@"[delivery-flow][yamap] apply marker icons finished count=%lu updatedCount=%lu iconKey=%@ durationMs=%.0f",
          (unsigned long)markerCount,
          (unsigned long)updatedCount,
          requestedIconKey ?: @"all",
          (RNCYMNow() - startedAt) * 1000.0);
}

- (void)applyClusteredMarkerIcons {
    [self applyClusteredMarkerIconsForIconKey:nil];
}

- (void)loadClusteredMarkerIconForKey:(NSString *)iconKey source:(NSString *)source {
    if (iconKey.length == 0 || source.length == 0) {
        return;
    }

    NSLog(@"[delivery-flow][yamap] marker icon load started iconKey=%@ sourceLength=%lu",
          iconKey,
          (unsigned long)source.length);

    dispatch_async(dispatch_get_global_queue(QOS_CLASS_USER_INITIATED, 0), ^{
        NSTimeInterval startedAt = RNCYMNow();
        NSURL *url = [NSURL URLWithString:source];
        if (url == nil) {
            NSLog(@"[delivery-flow][yamap] marker icon load failed iconKey=%@ reason=invalid_url", iconKey);
            return;
        }

        NSData *imageData = [NSData dataWithContentsOfURL:url];
        if (imageData == nil) {
            NSLog(@"[delivery-flow][yamap] marker icon load failed iconKey=%@ reason=no_data durationMs=%.0f",
                  iconKey,
                  (RNCYMNow() - startedAt) * 1000.0);
            return;
        }

        UIImage *image = [UIImage imageWithData:imageData];
        if (image == nil) {
            NSLog(@"[delivery-flow][yamap] marker icon load failed iconKey=%@ reason=decode_failed bytes=%lu durationMs=%.0f",
                  iconKey,
                  (unsigned long)imageData.length,
                  (RNCYMNow() - startedAt) * 1000.0);
            return;
        }

        dispatch_async(dispatch_get_main_queue(), ^{
            NSString *currentSource = self->clusteredMarkerIconSources[iconKey];
            if (![currentSource isEqualToString:source]) {
                NSLog(@"[delivery-flow][yamap] marker icon load ignored stale iconKey=%@ durationMs=%.0f",
                      iconKey,
                      (RNCYMNow() - startedAt) * 1000.0);
                return;
            }

            NSLog(@"[delivery-flow][yamap] marker icon load finished iconKey=%@ bytes=%lu durationMs=%.0f",
                  iconKey,
                  (unsigned long)imageData.length,
                  (RNCYMNow() - startedAt) * 1000.0);
            self->clusteredMarkerOriginalIconCache[iconKey] = image;
            [self->clusteredMarkerDisplayIconCache removeObjectForKey:iconKey];
            [self applyClusteredMarkerIconsForIconKey:iconKey];
        });
    });
}

-(UIImage*)clusterImage:(NSNumber*)clusterSize {
    NSString *text = [clusterSize stringValue];
    CGFloat fontSize = 17.0;
    CGFloat bubbleHeight = 42.0;
    CGFloat horizontalPadding = 14.0;
    CGFloat borderWidth = 2.0;
    UIFont *font = [UIFont systemFontOfSize:fontSize weight:UIFontWeightSemibold];
    CGSize textSize = [text sizeWithAttributes:@{NSFontAttributeName: font}];
    CGFloat bubbleWidth = MAX(bubbleHeight, ceil(textSize.width + horizontalPadding * 2.0));
    CGSize canvasSize = CGSizeMake(bubbleWidth + borderWidth * 2.0, bubbleHeight + borderWidth * 2.0);
    CGRect bubbleRect = CGRectMake(borderWidth, borderWidth, bubbleWidth, bubbleHeight);
    UIColor *resolvedClusterColor = clusterColor ?: [RNCYMView colorFromHexString:@"#00A0E3"];

    UIGraphicsBeginImageContextWithOptions(canvasSize, NO, 0.0);

    UIBezierPath *bubblePath = [UIBezierPath bezierPathWithRoundedRect:bubbleRect cornerRadius:bubbleHeight / 2.0];
    [resolvedClusterColor setFill];
    [bubblePath fill];

    bubblePath.lineWidth = borderWidth;
    [[UIColor colorWithWhite:1.0 alpha:0.95] setStroke];
    [bubblePath stroke];

    NSMutableParagraphStyle *paragraphStyle = [[NSMutableParagraphStyle alloc] init];
    paragraphStyle.alignment = NSTextAlignmentCenter;

    CGRect textRect = CGRectMake(
        CGRectGetMinX(bubbleRect),
        CGRectGetMidY(bubbleRect) - textSize.height / 2.0 - 0.5,
        CGRectGetWidth(bubbleRect),
        textSize.height
    );
    [text drawInRect:textRect withAttributes:@{
        NSFontAttributeName: font,
        NSForegroundColorAttributeName: UIColor.whiteColor,
        NSParagraphStyleAttributeName: paragraphStyle,
    }];

    UIImage *newImage = UIGraphicsGetImageFromCurrentImageContext();
    UIGraphicsEndImageContext();

    return newImage;
}

- (void)onClusterAddedWithCluster:(nonnull YMKCluster *)cluster {
    if (![NSThread isMainThread]) {
        RNCYMDispatchToMain(^{
            [self onClusterAddedWithCluster:cluster];
        });
        return;
    }

    clusterAddedLogCount += 1;
    NSNumber *clusterSize = @([cluster size]);
    BOOL shouldLogCluster = clusterAddedLogCount <= 20 || clusterAddedLogCount % 100 == 0;
    if (shouldLogCluster) {
        NSLog(@"[delivery-flow][yamap] cluster appearance update started sequence=%lu clusterSize=%@ thread=%@",
              (unsigned long)clusterAddedLogCount,
              clusterSize,
              RNCYMThreadName());
    }
    [[cluster appearance] setIconWithImage:[self clusterImage:clusterSize]];
    [cluster addClusterTapListenerWithClusterTapListener:self];
    if (shouldLogCluster) {
        NSLog(@"[delivery-flow][yamap] cluster appearance update finished sequence=%lu clusterSize=%@",
              (unsigned long)clusterAddedLogCount,
              clusterSize);
    }
}

- (BOOL)onClusterTapWithCluster:(nonnull YMKCluster *)cluster {
    if (![NSThread isMainThread]) {
        RNCYMDispatchToMain(^{
            [self onClusterTapWithCluster:cluster];
        });
        return YES;
    }

    NSMutableArray<YMKPoint*>* lastKnownMarkers = [[NSMutableArray alloc] init];
    for (YMKPlacemarkMapObject *placemark in [cluster placemarks]) {
        [lastKnownMarkers addObject:[placemark geometry]];
    }
    NSLog(@"[delivery-flow][yamap] cluster tapped placemarkCount=%lu thread=%@",
          (unsigned long)lastKnownMarkers.count,
          RNCYMThreadName());
    [self fitMarkers:lastKnownMarkers];
    return YES;
}

- (BOOL)onMapObjectTapWithMapObject:(nonnull YMKMapObject *)mapObject point:(nonnull YMKPoint *)point {
    if (![NSThread isMainThread]) {
        RNCYMDispatchToMain(^{
            [self onMapObjectTapWithMapObject:mapObject point:point];
        });
        return YES;
    }

    if (!self.onMarkerPress || ![mapObject isKindOfClass:[YMKPlacemarkMapObject class]]) {
        return YES;
    }

    NSUInteger index = [placemarks indexOfObjectIdenticalTo:(YMKPlacemarkMapObject *)mapObject];
    if (index == NSNotFound || index >= placemarkPayloads.count) {
        return YES;
    }

    NSDictionary *payload = placemarkPayloads[index];
    NSMutableDictionary *event = [[NSMutableDictionary alloc] initWithDictionary:@{
        @"point": @{
            @"lat": @(point.latitude),
            @"lon": @(point.longitude),
        }
    }];

    NSString *iconKey = [payload[@"iconKey"] isKindOfClass:[NSString class]] ? payload[@"iconKey"] : nil;
    if (iconKey.length > 0) {
        event[@"iconKey"] = iconKey;
    }

    NSDictionary *data = [payload[@"data"] isKindOfClass:[NSDictionary class]] ? payload[@"data"] : nil;
    if (data != nil) {
        event[@"data"] = data;
    }

    NSLog(@"[delivery-flow][yamap] marker tapped iconKey=%@ code=%@ provider=%@ thread=%@",
          iconKey ?: @"unknown",
          [data[@"code"] isKindOfClass:[NSString class]] ? data[@"code"] : @"unknown",
          [data[@"provider"] isKindOfClass:[NSString class]] ? data[@"provider"] : @"unknown",
          RNCYMThreadName());
    self.onMarkerPress(event);
    return YES;
}

- (void)onCameraPositionChangedWithMap:(nonnull YMKMap*)map
                        cameraPosition:(nonnull YMKCameraPosition*)cameraPosition
                    cameraUpdateReason:(YMKCameraUpdateReason)cameraUpdateReason
                              finished:(BOOL)finished {
    cameraPositionEventCount += 1;
    if (finished || cameraPositionEventCount <= 20 || cameraPositionEventCount % 120 == 0) {
        NSLog(@"[delivery-flow][yamap] camera position event sequence=%lu lat=%.6f lon=%.6f zoom=%.2f reason=%@ finished=%d thread=%@",
              (unsigned long)cameraPositionEventCount,
              cameraPosition.target.latitude,
              cameraPosition.target.longitude,
              cameraPosition.zoom,
              cameraUpdateReason == 0 ? @"GESTURES" : @"APPLICATION",
              finished,
              RNCYMThreadName());
    }

    [super onCameraPositionChangedWithMap:map cameraPosition:cameraPosition cameraUpdateReason:cameraUpdateReason finished:finished];
}

- (void)onMapLoadedWithStatistics:(YMKMapLoadStatistics*)statistics {
    mapLoadedEventCount += 1;
    NSLog(@"[delivery-flow][yamap] map loaded sequence=%lu renderObjectCount=%lu fullyLoaded=%d fullyAppeared=%d tileMemoryUsage=%lu thread=%@",
          (unsigned long)mapLoadedEventCount,
          (unsigned long)statistics.renderObjectCount,
          statistics.fullyLoaded,
          statistics.fullyAppeared,
          (unsigned long)statistics.tileMemoryUsage,
          RNCYMThreadName());

    [super onMapLoadedWithStatistics:statistics];
}

- (void)onTrafficChangedWithTrafficLevel:(nullable YMKTrafficLevel *)trafficLevel {
}

- (void)onTrafficLoading {
}

- (void)onTrafficExpired {
}

- (void)setInitialRegion:(NSDictionary *)initialParams {
    if (![NSThread isMainThread]) {
        NSDictionary *initialParamsSnapshot = [initialParams isKindOfClass:[NSDictionary class]]
            ? [initialParams copy]
            : nil;
        RNCYMDispatchToMain(^{
            [self setInitialRegion:initialParamsSnapshot];
        });
        return;
    }

    if (initializedRegion) return;
    if ([initialParams valueForKey:@"lat"] == nil || [initialParams valueForKey:@"lon"] == nil) return;

    float initialZoom = 10.f;
    float initialAzimuth = 0.f;
    float initialTilt = 0.f;

    if ([initialParams valueForKey:@"zoom"] != nil) initialZoom = [initialParams[@"zoom"] floatValue];
    if ([initialParams valueForKey:@"azimuth"] != nil) initialTilt = [initialParams[@"azimuth"] floatValue];
    if ([initialParams valueForKey:@"tilt"] != nil) initialTilt = [initialParams[@"tilt"] floatValue];

    YMKPoint *initialRegionCenter = [RCTConvert YMKPoint:@{@"lat" : [initialParams valueForKey:@"lat"], @"lon" : [initialParams valueForKey:@"lon"]}];
    YMKCameraPosition *initialRegionPosition = [YMKCameraPosition cameraPositionWithTarget:initialRegionCenter zoom:initialZoom azimuth:initialAzimuth tilt:initialTilt];
    NSLog(@"[delivery-flow][yamap] initial region move started lat=%.6f lon=%.6f zoom=%.2f thread=%@",
          initialRegionCenter.latitude,
          initialRegionCenter.longitude,
          initialZoom,
          RNCYMThreadName());
    [self.mapWindow.map moveWithCameraPosition:initialRegionPosition];
    initializedRegion = YES;
    NSLog(@"[delivery-flow][yamap] initial region move finished");
}

@synthesize reactTag;

@end
