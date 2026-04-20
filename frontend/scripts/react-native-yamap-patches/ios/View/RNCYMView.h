#ifndef RNCYMView_h
#define RNCYMView_h
#import <React/RCTComponent.h>

#import <MapKit/MapKit.h>
#import <RNYMView.h>
@import YandexMapsMobile;

@class RCTBridge;

@interface RNCYMView: RNYMView<YMKClusterListener, YMKClusterTapListener, YMKMapObjectTapListener>

@property (nonatomic, copy) RCTBubblingEventBlock onMarkerPress;

- (void)setClusterColor:(UIColor*_Nullable)color;
- (void)setMarkerSize:(CGFloat)markerSize;
- (void)setClusteredMarkerIcons:(NSDictionary<NSString *, NSString *> *_Nullable)icons;
- (void)setClusteredMarkers:(NSArray<NSDictionary *> *_Nonnull)points;
- (void)setInitialRegion:(NSDictionary *_Nullable)initialRegion;

@end

#endif /* RNYMView_h */
