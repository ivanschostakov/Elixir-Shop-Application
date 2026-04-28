#import <React/RCTViewManager.h>
#import <MapKit/MapKit.h>
#import <math.h>
#import "Converter/RCTConvert+Yamap.m"
#import "ClusteredYamapView.h"
#import "RNYamap.h"
#import "View/RNCYMView.h"

#ifndef MAX
#import <NSObjCRuntime.h>
#endif

static inline void RNCYMManagerDispatchToMain(dispatch_block_t block) {
    if ([NSThread isMainThread]) {
        block();
    } else {
        dispatch_async(dispatch_get_main_queue(), block);
    }
}

static inline NSString *RNCYMManagerThreadName(void) {
    return [NSThread isMainThread] ? @"main" : @"background";
}

@implementation ClusteredYamapView

RCT_EXPORT_MODULE()

- (NSArray<NSString *> *)supportedEvents {
    return @[
        @"onRouteFound",
        @"onCameraPositionReceived",
        @"onVisibleRegionReceived",
        @"onCameraPositionChange",
        @"onMapPress",
        @"onMapLongPress",
        @"onCameraPositionChangeEnd",
        @"onMarkerPress",
        @"onMapLoaded",
        @"onWorldToScreenPointsReceived",
        @"onScreenToWorldPointsReceived"
    ];
}

- (instancetype)init {
    self = [super init];
    return self;
}
+ (BOOL)requiresMainQueueSetup {
    return YES;
}

- (UIView *_Nullable)view {
    NSLog(@"[delivery-flow][yamap-manager] native clustered map view creation requested thread=%@", RNCYMManagerThreadName());
    RNCYMView* map = [[RNCYMView alloc] init];
    NSLog(@"[delivery-flow][yamap-manager] native clustered map view created thread=%@", RNCYMManagerThreadName());
    return map;
}

- (void)setCenterForMap:(RNCYMView*)map center:(NSDictionary*)_center zoom:(float)zoom azimuth:(float)azimuth tilt:(float)tilt duration:(float)duration animation:(int)animation {
    NSLog(@"[delivery-flow][yamap-manager] setCenter requested lat=%@ lon=%@ zoom=%.2f duration=%.2f animation=%d thread=%@",
          _center[@"lat"],
          _center[@"lon"],
          zoom,
          duration,
          animation,
          RNCYMManagerThreadName());
    YMKPoint *center = [RCTConvert YMKPoint:_center];
    YMKCameraPosition *pos = [YMKCameraPosition cameraPositionWithTarget:center zoom:zoom azimuth:azimuth tilt:tilt];
    [map setCenter:pos withDuration:duration withAnimation:animation];
}

// props
RCT_EXPORT_VIEW_PROPERTY(onRouteFound, RCTBubblingEventBlock)
RCT_EXPORT_VIEW_PROPERTY(onCameraPositionReceived, RCTBubblingEventBlock)
RCT_EXPORT_VIEW_PROPERTY(onVisibleRegionReceived, RCTBubblingEventBlock)
RCT_EXPORT_VIEW_PROPERTY(onCameraPositionChange, RCTBubblingEventBlock)
RCT_EXPORT_VIEW_PROPERTY(onMapPress, RCTBubblingEventBlock)
RCT_EXPORT_VIEW_PROPERTY(onMapLongPress, RCTBubblingEventBlock)
RCT_EXPORT_VIEW_PROPERTY(onCameraPositionChangeEnd, RCTBubblingEventBlock)
RCT_EXPORT_VIEW_PROPERTY(onMapLoaded, RCTBubblingEventBlock)
RCT_EXPORT_VIEW_PROPERTY(onMarkerPress, RCTBubblingEventBlock)
RCT_EXPORT_VIEW_PROPERTY(onWorldToScreenPointsReceived, RCTBubblingEventBlock)
RCT_EXPORT_VIEW_PROPERTY(onScreenToWorldPointsReceived, RCTBubblingEventBlock)

RCT_CUSTOM_VIEW_PROPERTY(initialRegion, NSDictionary, RNYMView) {
    if (json && view) {
        NSDictionary *initialRegion = [json isKindOfClass:[NSDictionary class]] ? [json copy] : nil;
        NSLog(@"[delivery-flow][yamap-manager] initialRegion prop received lat=%@ lon=%@ zoom=%@ thread=%@",
              initialRegion[@"lat"],
              initialRegion[@"lon"],
              initialRegion[@"zoom"],
              RNCYMManagerThreadName());
        RNCYMManagerDispatchToMain(^{
            [view setInitialRegion:initialRegion];
        });
    }
}
RCT_CUSTOM_VIEW_PROPERTY(userLocationAccuracyFillColor, NSNumber, RNCYMView) {
    UIColor *color = [RCTConvert UIColor:json];
    RNCYMManagerDispatchToMain(^{
        [view setUserLocationAccuracyFillColor:color];
    });
}

RCT_CUSTOM_VIEW_PROPERTY(clusterColor, NSNumber, RNCYMView) {
    UIColor *color = [RCTConvert UIColor:json];
    NSLog(@"[delivery-flow][yamap-manager] clusterColor prop received hasColor=%d thread=%@",
          color != nil,
          RNCYMManagerThreadName());
    RNCYMManagerDispatchToMain(^{
        [view setClusterColor:color];
    });
}

RCT_CUSTOM_VIEW_PROPERTY(markerSize, NSNumber, RNCYMView) {
    CGFloat markerSize = json ? [json floatValue] : 34.0f;
    NSLog(@"[delivery-flow][yamap-manager] markerSize prop received size=%.2f thread=%@",
          markerSize,
          RNCYMManagerThreadName());
    RNCYMManagerDispatchToMain(^{
        [view setMarkerSize:markerSize];
    });
}

RCT_CUSTOM_VIEW_PROPERTY(clusteredMarkers, NSArray<YMKRequestPoint*>*_Nonnull, RNCYMView) {
    NSArray *markers = [RCTConvert NSArray:json];
    NSLog(@"[delivery-flow][yamap-manager] clusteredMarkers prop received count=%lu thread=%@",
          (unsigned long)markers.count,
          RNCYMManagerThreadName());
    [view setClusteredMarkers:markers];
}

RCT_CUSTOM_VIEW_PROPERTY(clusteredMarkerIcons, NSDictionary, RNCYMView) {
    NSLog(@"[delivery-flow][yamap-manager] clusteredMarkerIcons prop received valid=%d count=%lu thread=%@",
          json && [json isKindOfClass:[NSDictionary class]],
          json && [json isKindOfClass:[NSDictionary class]] ? (unsigned long)((NSDictionary *)json).count : 0,
          RNCYMManagerThreadName());
    if (json && [json isKindOfClass:[NSDictionary class]]) {
        NSDictionary *icons = [(NSDictionary *)json copy];
        [view setClusteredMarkerIcons:icons];
        return;
    }

    [view setClusteredMarkerIcons:nil];
}

RCT_CUSTOM_VIEW_PROPERTY(userLocationAccuracyStrokeColor, NSNumber, RNCYMView) {
    UIColor *color = [RCTConvert UIColor:json];
    RNCYMManagerDispatchToMain(^{
        [view setUserLocationAccuracyStrokeColor:color];
    });
}


RCT_CUSTOM_VIEW_PROPERTY(userLocationAccuracyStrokeWidth, NSNumber, RNCYMView) {
    CGFloat strokeWidth = json ? [json floatValue] : 0.0f;
    RNCYMManagerDispatchToMain(^{
        [view setUserLocationAccuracyStrokeWidth:strokeWidth];
    });
}

RCT_CUSTOM_VIEW_PROPERTY(userLocationIcon, NSString, RNCYMView) {
    if (json && view) {
        NSString *icon = [json copy];
        RNCYMManagerDispatchToMain(^{
            [view setUserLocationIcon:icon];
        });
    }
}

RCT_CUSTOM_VIEW_PROPERTY(userLocationIconScale, NSNumber, RNCYMView) {
    if (json && view) {
        NSNumber *iconScale = [json copy];
        RNCYMManagerDispatchToMain(^{
            [view setUserLocationIconScale:iconScale];
        });
    }
}

RCT_CUSTOM_VIEW_PROPERTY(showUserPosition, BOOL, RNCYMView) {
    if (view) {
        BOOL showUserPosition = json ? [json boolValue] : NO;
        NSLog(@"[delivery-flow][yamap-manager] showUserPosition prop received value=%d thread=%@",
              showUserPosition,
              RNCYMManagerThreadName());
        RNCYMManagerDispatchToMain(^{
            [view setListenUserLocation:showUserPosition];
        });
    }
}

RCT_CUSTOM_VIEW_PROPERTY(followUser, BOOL, RNCYMView) {
    BOOL followUser = json ? [json boolValue] : NO;
    NSLog(@"[delivery-flow][yamap-manager] followUser prop received value=%d thread=%@",
          followUser,
          RNCYMManagerThreadName());
    RNCYMManagerDispatchToMain(^{
        [view setFollowUser:followUser];
    });
}

RCT_CUSTOM_VIEW_PROPERTY(nightMode, BOOL, RNCYMView) {
    if (view) {
        BOOL nightMode = json ? [json boolValue]: NO;
        RNCYMManagerDispatchToMain(^{
            [view setNightMode:nightMode];
        });
    }
}

RCT_CUSTOM_VIEW_PROPERTY(mapStyle, NSString, RNCYMView) {
    if (json && view) {
        NSString *mapStyle = [json copy];
        NSLog(@"[delivery-flow][yamap-manager] mapStyle prop received length=%lu thread=%@",
              (unsigned long)mapStyle.length,
              RNCYMManagerThreadName());
        RNCYMManagerDispatchToMain(^{
            [view.mapWindow.map setMapStyleWithStyle:mapStyle];
        });
    }
}

RCT_CUSTOM_VIEW_PROPERTY(zoomGesturesEnabled, BOOL, RNCYMView) {
    if (view) {
        BOOL enabled = json ? [json boolValue] : YES;
        RNCYMManagerDispatchToMain(^{
            view.mapWindow.map.zoomGesturesEnabled = enabled;
        });
    }
}

RCT_CUSTOM_VIEW_PROPERTY(scrollGesturesEnabled, BOOL, RNCYMView) {
    if (view) {
        BOOL enabled = json ? [json boolValue] : YES;
        RNCYMManagerDispatchToMain(^{
            view.mapWindow.map.scrollGesturesEnabled = enabled;
        });
    }
}

RCT_CUSTOM_VIEW_PROPERTY(tiltGesturesEnabled, BOOL, RNCYMView) {
    if (view) {
        BOOL enabled = json ? [json boolValue] : YES;
        RNCYMManagerDispatchToMain(^{
            view.mapWindow.map.tiltGesturesEnabled = enabled;
        });
    }
}

RCT_CUSTOM_VIEW_PROPERTY(rotateGesturesEnabled, BOOL, RNCYMView) {
    if (view) {
        BOOL enabled = json ? [json boolValue] : YES;
        RNCYMManagerDispatchToMain(^{
            view.mapWindow.map.rotateGesturesEnabled = enabled;
        });
    }
}

RCT_CUSTOM_VIEW_PROPERTY(fastTapEnabled, BOOL, RNCYMView) {
    if (view) {
        BOOL enabled = json ? [json boolValue] : YES;
        RNCYMManagerDispatchToMain(^{
            view.mapWindow.map.fastTapEnabled = enabled;
        });
    }
}

RCT_CUSTOM_VIEW_PROPERTY(mapType, NSString, RNCYMView) {
    if (view) {
        NSString *mapType = [json copy];
        NSLog(@"[delivery-flow][yamap-manager] mapType prop received value=%@ thread=%@",
              mapType,
              RNCYMManagerThreadName());
        RNCYMManagerDispatchToMain(^{
            [view setMapType:mapType];
        });
    }
}

// ref
RCT_EXPORT_METHOD(fitAllMarkers:(nonnull NSNumber*) reactTag) {
    [self.bridge.uiManager addUIBlock:^(RCTUIManager *uiManager, NSDictionary<NSNumber *,UIView *> *viewRegistry) {
        RNCYMView *view = (RNCYMView*) viewRegistry[reactTag];
        if (!view || ![view isKindOfClass:[RNCYMView class]]) {
            RCTLogError(@"Cannot find NativeView with tag #%@", reactTag);
            return;
        }
        [view fitAllMarkers];
    }];
}

RCT_EXPORT_METHOD(fitMarkers:(nonnull NSNumber *)reactTag json:(id)json) {
    [self.bridge.uiManager addUIBlock:^(RCTUIManager *uiManager, NSDictionary<NSNumber *, UIView*> *viewRegistry) {
        RNYMView *view = (RNYMView *)viewRegistry[reactTag];

        if (!view || ![view isKindOfClass:[RNYMView class]]) {
            RCTLogError(@"Cannot find NativeView with tag #%@", reactTag);
            return;
        }

        NSArray<YMKPoint *> *points = [RCTConvert Points:json];
        [view fitMarkers: points];
    }];
}

RCT_EXPORT_METHOD(findRoutes:(nonnull NSNumber*) reactTag json:(NSDictionary*) json) {
    [self.bridge.uiManager addUIBlock:^(RCTUIManager *uiManager, NSDictionary<NSNumber *,UIView *> *viewRegistry) {
        RNCYMView *view = (RNCYMView*) viewRegistry[reactTag];
        if (!view || ![view isKindOfClass:[RNCYMView class]]) {
            RCTLogError(@"Cannot find NativeView with tag #%@", reactTag);
            return;
        }
        NSArray<YMKPoint*>* points = [RCTConvert Points:json[@"points"]];
        NSMutableArray<YMKRequestPoint*>* requestPoints = [[NSMutableArray alloc] init];
        for (int i = 0; i < [points count]; ++i) {
            YMKRequestPoint * requestPoint = [YMKRequestPoint requestPointWithPoint:[points objectAtIndex:i] type: YMKRequestPointTypeWaypoint pointContext:nil drivingArrivalPointId:nil];
            [requestPoints addObject:requestPoint];
        }
        NSArray<NSString*>* vehicles = [RCTConvert Vehicles:json[@"vehicles"]];
        [view findRoutes: requestPoints vehicles: vehicles withId:json[@"id"]];
    }];
}

RCT_EXPORT_METHOD(setCenter:(nonnull NSNumber*) reactTag center:(NSDictionary*_Nonnull) center zoom:(NSNumber*_Nonnull) zoom azimuth:(NSNumber*_Nonnull) azimuth tilt:(NSNumber*_Nonnull) tilt duration: (NSNumber*_Nonnull) duration animation:(NSNumber*_Nonnull) animation) {
    [self.bridge.uiManager addUIBlock:^(RCTUIManager *uiManager, NSDictionary<NSNumber *,UIView *> *viewRegistry) {
        RNCYMView *view = (RNCYMView*) viewRegistry[reactTag];
        if (!view || ![view isKindOfClass:[RNCYMView class]]) {
            RCTLogError(@"Cannot find NativeView with tag #%@", reactTag);
            return;
        }
        [self setCenterForMap: view center:center zoom: [zoom floatValue] azimuth: [azimuth floatValue] tilt: [tilt floatValue] duration: [duration floatValue] animation: [animation intValue]];
    }];
}

RCT_EXPORT_METHOD(setZoom:(nonnull NSNumber*) reactTag zoom:(NSNumber*_Nonnull) zoom duration:(NSNumber*_Nonnull) duration animation:(NSNumber*_Nonnull) animation) {
    [self.bridge.uiManager addUIBlock:^(RCTUIManager *uiManager, NSDictionary<NSNumber *,UIView *> *viewRegistry) {
        RNCYMView *view = (RNCYMView*) viewRegistry[reactTag];
        if (!view || ![view isKindOfClass:[RNCYMView class]]) {
            RCTLogError(@"Cannot find NativeView with tag #%@", reactTag);
            return;
        }
        [view setZoom: [zoom floatValue] withDuration:[duration floatValue] withAnimation:[animation intValue]];
    }];
}

RCT_EXPORT_METHOD(getCameraPosition:(nonnull NSNumber*) reactTag _id:(NSString*_Nonnull) _id) {
    [self.bridge.uiManager addUIBlock:^(RCTUIManager *uiManager, NSDictionary<NSNumber *,UIView *> *viewRegistry) {
        RNCYMView *view = (RNCYMView*) viewRegistry[reactTag];
        if (!view || ![view isKindOfClass:[RNCYMView class]]) {
            RCTLogError(@"Cannot find NativeView with tag #%@", reactTag);
            return;
        }
        [view emitCameraPositionToJS:_id];
    }];
}

RCT_EXPORT_METHOD(getVisibleRegion:(nonnull NSNumber*) reactTag _id:(NSString*_Nonnull) _id) {
    [self.bridge.uiManager addUIBlock:^(RCTUIManager *uiManager, NSDictionary<NSNumber *,UIView *> *viewRegistry) {
        RNCYMView *view = (RNCYMView*) viewRegistry[reactTag];
        if (!view || ![view isKindOfClass:[RNCYMView class]]) {
            RCTLogError(@"Cannot find NativeView with tag #%@", reactTag);
            return;
        }
        [view emitVisibleRegionToJS:_id];
    }];
}

RCT_EXPORT_METHOD(setTrafficVisible:(nonnull NSNumber *)reactTag traffic:(BOOL)traffic) {
    [self.bridge.uiManager addUIBlock:^(RCTUIManager *uiManager, NSDictionary<NSNumber *, UIView *> *viewRegistry) {
        RNCYMView *view = (RNCYMView *)viewRegistry[reactTag];

        if (!view || ![view isKindOfClass:[RNCYMView class]]) {
            RCTLogError(@"Cannot find NativeView with tag #%@", reactTag);
            return;
        }

        [view setTrafficVisible:traffic];
    }];
}

RCT_EXPORT_METHOD(getScreenPoints:(nonnull NSNumber *)reactTag json:(id)json _id:(NSString *_Nonnull)_id) {
    [self.bridge.uiManager addUIBlock:^(RCTUIManager *uiManager, NSDictionary<NSNumber *, UIView *> *viewRegistry) {
        RNCYMView *view = (RNCYMView *)viewRegistry[reactTag];

        if (!view || ![view isKindOfClass:[RNCYMView class]]) {
            RCTLogError(@"Cannot find NativeView with tag #%@", reactTag);
            return;
        }

        NSArray<YMKPoint *> *mapPoints = [RCTConvert Points:json];
        [view emitWorldToScreenPoint:mapPoints withId:_id];
    }];
}

RCT_EXPORT_METHOD(getWorldPoints:(nonnull NSNumber *)reactTag json:(id)json _id:(NSString *_Nonnull)_id) {
    [self.bridge.uiManager addUIBlock:^(RCTUIManager *uiManager, NSDictionary<NSNumber *, UIView *> *viewRegistry) {
        RNCYMView *view = (RNCYMView *)viewRegistry[reactTag];

        if (!view || ![view isKindOfClass:[RNCYMView class]]) {
            RCTLogError(@"Cannot find NativeView with tag #%@", reactTag);
            return;
        }

        NSArray<YMKScreenPoint *> *screenPoints = [RCTConvert ScreenPoints:json];
        [view emitScreenToWorldPoint:screenPoints withId:_id];
    }];
}

@end
