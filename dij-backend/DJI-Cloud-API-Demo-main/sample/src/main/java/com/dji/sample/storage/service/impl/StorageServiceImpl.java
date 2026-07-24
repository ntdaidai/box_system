package com.dji.sample.storage.service.impl;

import com.dji.sample.component.oss.model.OssConfiguration;
import com.dji.sample.component.oss.service.impl.OssServiceContext;
import com.dji.sample.storage.service.IStorageService;
import com.dji.sdk.cloudapi.media.StorageConfigGet;
import com.dji.sdk.cloudapi.media.api.AbstractMediaService;
import com.dji.sdk.cloudapi.storage.StsCredentialsResponse;
import com.dji.sdk.mqtt.MqttReply;
import com.dji.sdk.mqtt.requests.TopicRequestsRequest;
import com.dji.sdk.mqtt.requests.TopicRequestsResponse;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.messaging.MessageHeaders;
import org.springframework.stereotype.Service;

import java.time.LocalDate;
import java.time.format.DateTimeFormatter;

/**
 * @author sean
 * @version 0.3
 * @date 2022/3/9
 */
@Service
public class StorageServiceImpl extends AbstractMediaService implements IStorageService {

    @Autowired
    private OssServiceContext ossService;

    // 日期格式：yyyy-MM-dd
    private static final DateTimeFormatter DATE_FORMATTER = DateTimeFormatter.ofPattern("yyyy-MM-dd");

    @Override
    public StsCredentialsResponse getSTSCredentials() {
        // 生成带日期目录的前缀，例如：media/2026-07-23
        String datePrefix = OssConfiguration.objectDirPrefix + "/"
                + LocalDate.now().format(DATE_FORMATTER);

        return new StsCredentialsResponse()
                .setEndpoint(OssConfiguration.endpoint)
                .setBucket(OssConfiguration.bucket)
                .setCredentials(ossService.getCredentials())
                .setProvider(OssConfiguration.provider)
                .setObjectKeyPrefix(datePrefix)
                .setRegion(OssConfiguration.region);
    }

    @Override
    public TopicRequestsResponse<MqttReply<StsCredentialsResponse>> storageConfigGet(TopicRequestsRequest<StorageConfigGet> response, MessageHeaders headers) {
        return new TopicRequestsResponse<MqttReply<StsCredentialsResponse>>().setData(MqttReply.success(getSTSCredentials()));
    }
}
