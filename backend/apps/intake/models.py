import uuid
from django.db import models


class Material(models.Model):
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    title=models.CharField(max_length=500,blank=True)
    is_demo=models.BooleanField(default=False)
    created_by=models.ForeignKey("personnel.Employee",on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)


class Receipt(models.Model):
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    received_at=models.DateField()
    sender_name=models.CharField(max_length=500,blank=True)
    material=models.ForeignKey(Material,related_name="receipts",on_delete=models.PROTECT)
    basis_document=models.ForeignKey("documents.Document",related_name="receipts",null=True,blank=True,on_delete=models.PROTECT)
    department=models.ForeignKey("references.Department",null=True,blank=True,on_delete=models.PROTECT)
    created_by=models.ForeignKey("personnel.Employee",on_delete=models.PROTECT)
    status=models.CharField(max_length=20,choices=[("draft","Уточнение комплекта"),("accepted","Принято"),("historical","Перенесено из журнала")],default="draft")
    version=models.PositiveIntegerField(default=1)
    created_at=models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering=["-received_at","id"]
