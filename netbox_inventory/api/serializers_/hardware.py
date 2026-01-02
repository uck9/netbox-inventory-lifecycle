from django.contrib.contenttypes.models import ContentType
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from netbox.api.fields import ContentTypeField
from netbox.api.serializers import NetBoxModelSerializer
from utilities.api import get_serializer_for_model

from netbox_inventory.models import HardwareLifecycle

__all__ = ('HardwareLifecycleSerializer',)


class HardwareLifecycleSerializer(NetBoxModelSerializer):
    url = serializers.HyperlinkedIdentityField(
        view_name='plugins-api:netbox_inventory-api:hardwarelifecycle-detail'
    )
    assigned_object_type = ContentTypeField(queryset=ContentType.objects.all())

    end_of_sale = serializers.DateField(required=False, allow_null=True)
    end_of_maintenance = serializers.DateField(required=False, allow_null=True)
    end_of_security = serializers.DateField(required=False, allow_null=True)
    last_contract_attach = serializers.DateField(required=False, allow_null=True)
    last_contract_renewal = serializers.DateField(required=False, allow_null=True)
    end_of_support = serializers.DateField(required=False, allow_null=True)
    notice_url = serializers.URLField(required=False)

    class Meta:
        model = HardwareLifecycle
        fields = (
            'url',
            'id',
            'display',
            'assigned_object_type',
            'assigned_object_id',
            'end_of_sale',
            'end_of_maintenance',
            'end_of_security',
            'last_contract_attach',
            'last_contract_renewal',
            'end_of_support',
            'notice_url',
            'description',
            'comments',
            'tags',
            'custom_fields',
        )
        brief_fields = (
            'url',
            'id',
            'display',
            'assigned_object_type',
            'assigned_object_id',
            'end_of_sale',
        )


    @extend_schema_field(serializers.JSONField(allow_null=True))
    def get_assigned_object(self, instance):
        serializer = get_serializer_for_model(instance.assigned_object)
        context = {'request': self.context['request']}
        return serializer(instance.assigned_object, context=context, nested=True).data