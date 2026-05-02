from rest_framework.throttling import SimpleRateThrottle


class ScopedIPRateThrottle(SimpleRateThrottle):
    scope = ""

    def get_cache_key(self, request, view):
        forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR", "")
        if forwarded_for:
            ident = forwarded_for.split(",")[0].strip()
        else:
            ident = self.get_ident(request)
        return self.cache_format % {"scope": self.scope, "ident": ident}


class SecureVideoStreamThrottle(ScopedIPRateThrottle):
    scope = "secure_video_stream"


class SecureVideoLikeThrottle(ScopedIPRateThrottle):
    scope = "secure_video_like"


class SecureVideoRatingThrottle(ScopedIPRateThrottle):
    scope = "secure_video_rating"


class SecureVideoUploadThrottle(ScopedIPRateThrottle):
    scope = "secure_video_upload"


class SecureVideoDownloadRequestThrottle(ScopedIPRateThrottle):
    scope = "secure_video_download_request"


class SecureVideoDownloadLinkThrottle(ScopedIPRateThrottle):
    scope = "secure_video_download_link"


class SecureOwnerReviewThrottle(ScopedIPRateThrottle):
    scope = "secure_owner_review"


class SecureOwnerNotificationsThrottle(ScopedIPRateThrottle):
    scope = "secure_owner_notifications"
