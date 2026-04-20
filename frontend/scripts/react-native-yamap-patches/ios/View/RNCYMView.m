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
    Boolean initializedRegion;
}

- (instancetype)init {
    self = [super init];
    placemarks = [[NSMutableArray alloc] init];
    placemarkPayloads = [[NSMutableArray alloc] init];
    clusteredMarkerIconSources = [[NSMutableDictionary alloc] init];
    clusteredMarkerOriginalIconCache = [[NSMutableDictionary alloc] init];
    clusteredMarkerDisplayIconCache = [[NSMutableDictionary alloc] init];
    clusteredMarkerDisplaySize = RNCYMDefaultClusteredMarkerDisplaySize;
    clusterColor = nil;
    clusterCollection = [self.mapWindow.map.mapObjects addClusterizedPlacemarkCollectionWithClusterListener:self];
    initializedRegion = NO;
    return self;
}

- (void)setClusterColor:(UIColor *)color {
    clusterColor = color;
    [clusterCollection clusterPlacemarksWithClusterRadius:50 minZoom:12];
}

- (void)setClusteredMarkerIcons:(NSDictionary<NSString *,NSString *> *)icons {
    [clusteredMarkerIconSources removeAllObjects];
    [clusteredMarkerOriginalIconCache removeAllObjects];
    [clusteredMarkerDisplayIconCache removeAllObjects];

    if (![icons isKindOfClass:[NSDictionary class]]) {
        [self applyClusteredMarkerIcons];
        return;
    }

    [clusteredMarkerIconSources addEntriesFromDictionary:icons];

    for (NSString *iconKey in clusteredMarkerIconSources) {
        NSString *source = clusteredMarkerIconSources[iconKey];
        [self loadClusteredMarkerIconForKey:iconKey source:source];
    }

    [self applyClusteredMarkerIcons];
}

- (void)setClusteredMarkers:(NSArray *)markers {
    [placemarks removeAllObjects];
    [placemarkPayloads removeAllObjects];
    [clusterCollection clear];

    if (![markers isKindOfClass:[NSArray class]] || markers.count == 0) {
        return;
    }

    NSMutableArray<YMKPoint *> *points = [[NSMutableArray alloc] init];
    NSMutableArray<NSDictionary *> *normalizedMarkers = [[NSMutableArray alloc] init];

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

        [points addObject:[YMKPoint pointWithLatitude:[latitude doubleValue] longitude:[longitude doubleValue]]];
        [normalizedMarkers addObject:@{
            @"point": @{
                @"lat": latitude,
                @"lon": longitude,
            },
            @"iconKey": iconKey,
            @"data": data ?: @{},
        }];
    }

    if (points.count == 0) {
        return;
    }

    NSString *firstIconKey = normalizedMarkers.firstObject[@"iconKey"];
    UIImage *placeholderImage = [self markerImageForIconKey:firstIconKey];
    NSArray<YMKPlacemarkMapObject *>* newPlacemarks = [clusterCollection addPlacemarksWithPoints:points image:placeholderImage style:[self markerIconStyle]];

    [placemarks addObjectsFromArray:newPlacemarks];
    [placemarkPayloads addObjectsFromArray:normalizedMarkers];

    for (YMKPlacemarkMapObject *placemark in placemarks) {
        [placemark addTapListenerWithTapListener:self];
    }

    [self applyClusteredMarkerIcons];
    [clusterCollection clusterPlacemarksWithClusterRadius:50 minZoom:12];
}

- (void)setMarkerSize:(CGFloat)markerSize {
    CGFloat resolvedMarkerSize = markerSize > 0.0 ? markerSize : RNCYMDefaultClusteredMarkerDisplaySize;
    if (fabs(clusteredMarkerDisplaySize - resolvedMarkerSize) < 0.5) {
        return;
    }

    clusteredMarkerDisplaySize = resolvedMarkerSize;
    [clusteredMarkerDisplayIconCache removeAllObjects];
    [self applyClusteredMarkerIcons];
}

- (void)onObjectRemovedWithView:(nonnull YMKUserLocationView *)view {
}

- (void)onMapTapWithMap:(nonnull YMKMap *)map
                  point:(nonnull YMKPoint *)point {
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

- (void)applyClusteredMarkerIcons {
    NSUInteger markerCount = MIN(placemarks.count, placemarkPayloads.count);
    for (NSUInteger index = 0; index < markerCount; index++) {
        YMKPlacemarkMapObject *placemark = placemarks[index];
        NSDictionary *payload = placemarkPayloads[index];
        NSString *iconKey = [payload[@"iconKey"] isKindOfClass:[NSString class]]
            ? payload[@"iconKey"]
            : RNCYMDefaultIconKey;
        UIImage *iconImage = [self markerImageForIconKey:iconKey];
        [placemark setIconWithImage:iconImage];
        [placemark setIconStyleWithStyle:[self markerIconStyle]];
    }
}

- (void)loadClusteredMarkerIconForKey:(NSString *)iconKey source:(NSString *)source {
    if (iconKey.length == 0 || source.length == 0) {
        return;
    }

    dispatch_async(dispatch_get_global_queue(QOS_CLASS_USER_INITIATED, 0), ^{
        NSURL *url = [NSURL URLWithString:source];
        if (url == nil) {
            return;
        }

        NSData *imageData = [NSData dataWithContentsOfURL:url];
        if (imageData == nil) {
            return;
        }

        UIImage *image = [UIImage imageWithData:imageData];
        if (image == nil) {
            return;
        }

        dispatch_async(dispatch_get_main_queue(), ^{
            NSString *currentSource = self->clusteredMarkerIconSources[iconKey];
            if (![currentSource isEqualToString:source]) {
                return;
            }

            self->clusteredMarkerOriginalIconCache[iconKey] = image;
            [self->clusteredMarkerDisplayIconCache removeObjectForKey:iconKey];
            [self applyClusteredMarkerIcons];
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
    NSNumber *clusterSize = @([cluster size]);
    [[cluster appearance] setIconWithImage:[self clusterImage:clusterSize]];
    [cluster addClusterTapListenerWithClusterTapListener:self];
}

- (BOOL)onClusterTapWithCluster:(nonnull YMKCluster *)cluster {
    NSMutableArray<YMKPoint*>* lastKnownMarkers = [[NSMutableArray alloc] init];
    for (YMKPlacemarkMapObject *placemark in [cluster placemarks]) {
        [lastKnownMarkers addObject:[placemark geometry]];
    }
    [self fitMarkers:lastKnownMarkers];
    return YES;
}

- (BOOL)onMapObjectTapWithMapObject:(nonnull YMKMapObject *)mapObject point:(nonnull YMKPoint *)point {
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

    self.onMarkerPress(event);
    return YES;
}

- (void)onTrafficChangedWithTrafficLevel:(nullable YMKTrafficLevel *)trafficLevel {
}

- (void)onTrafficLoading {
}

- (void)onTrafficExpired {
}

- (void)setInitialRegion:(NSDictionary *)initialParams {
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
    [self.mapWindow.map moveWithCameraPosition:initialRegionPosition];
    initializedRegion = YES;
}

@synthesize reactTag;

@end
