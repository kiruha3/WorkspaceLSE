import {computed} from 'vue'
import {useRoute,useRouter} from 'vue-router'
export function useRouteTableSort(options:{paginated?:boolean}={}){
 const route=useRoute(),router=useRouter()
 const ordering=computed(()=>typeof route.query.ordering==='string'?route.query.ordering:'')
 function sortTable(value:string){return router.replace({path:route.path,query:{...route.query,ordering:value||undefined,page:options.paginated===false?undefined:'1',...(options.paginated===false?{page_size:undefined}:{})}})}
 return {ordering,sortTable}
}
